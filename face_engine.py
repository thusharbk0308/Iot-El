import os
import cv2
import time
import csv
from datetime import datetime
import torch
import numpy as np
from facenet_pytorch import MTCNN, InceptionResnetV1
import config

class FaceEngine:
    def __init__(self):
        """
        Initializes the face recognition engine, ensures necessary project directories exist,
        and loads pre-trained MTCNN and InceptionResnetV1 models.
        """
        # Ensure directories exist
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        os.makedirs(config.MODELS_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
        
        self.device = torch.device("cpu")
        print(f"[ENGINE] Initializing FaceEngine on device: {self.device}")
        
        # Initialize MTCNN detector.
        # - keep_all=True detects multiple faces simultaneously.
        # - select_largest=False detects all faces rather than just the largest one.
        # - margin=14 adds a border buffer around detected faces to improve alignment/recognition.
        # - thresholds=[0.6, 0.7, 0.7] represents MTCNN's three network thresholds.
        self.detector = MTCNN(
            image_size=160,
            margin=14,
            min_face_size=40,
            thresholds=[0.6, 0.7, 0.7],
            keep_all=True,
            device=self.device
        )
        
        # Initialize InceptionResnetV1 (FaceNet model)
        # pretrained='vggface2' loaded for face embedding generation
        self.encoder = InceptionResnetV1(
            pretrained='vggface2',
            device=self.device
        ).eval()
        
        # State tracker for throttling unknown logs
        self.last_unknown_log_time = 0.0
        
    def detect_faces(self, frame):
        """
        Detect faces in a BGR frame from OpenCV.
        Args:
            frame: numpy array (BGR) of the input frame
        Returns:
            boxes: np.ndarray of shape (N, 4) containing [x1, y1, x2, y2] or None
            probs: np.ndarray of shape (N,) containing detection confidence or None
        """
        if frame is None:
            return None, None
        
        # Convert BGR frame to RGB for MTCNN
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Run MTCNN detection
        boxes, probs = self.detector.detect(frame_rgb)
        
        return boxes, probs
    
    def get_embedding(self, face_crop):
        """
        Extracts a L2-normalized face embedding from a face crop.
        Args:
            face_crop: numpy array (BGR) of the cropped face region
        Returns:
            embedding: 512-dimensional torch Tensor (L2 normalized)
        """
        # Convert BGR crop to RGB
        face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        
        # Resize to 160x160 as required by InceptionResnetV1
        face_resized = cv2.resize(face_rgb, (160, 160))
        
        # Convert to float tensor, shape (3, 160, 160)
        face_tensor = torch.tensor(face_resized, dtype=torch.float32).permute(2, 0, 1)
        
        # Normalize to range [-1, 1] (FaceNet expectation): (x - 127.5) / 128.0
        face_tensor = (face_tensor - 127.5) / 128.0
        
        # Generate embedding
        with torch.no_grad():
            embedding = self.encoder(face_tensor.unsqueeze(0)) # Shape: (1, 512)
            # L2-normalize the embedding vector
            embedding = embedding / embedding.norm(dim=1, keepdim=True)
            
        return embedding[0] # Shape: (512,)
    
    def compare_embeddings(self, embedding, database):
        """
        Compares input embedding with all enrolled users in the database using Cosine Similarity.
        Matches centroid first, and falls back to individual comparison if centroid matching fails.
        Args:
            embedding: torch.Tensor of shape (512,)
            database: dict mapping name -> {"centroid": Tensor, "individuals": Tensor}
        Returns:
            matched_name: str ("Unknown" or the person's name)
            confidence: float (similarity score percentage, 0.0 to 100.0)
        """
        best_name = "Unknown"
        best_similarity = 0.0
        
        for name, data in database.items():
            centroid = data["centroid"]
            individuals = data["individuals"]
            
            # Step 1: Centroid matching (primary)
            sim_centroid = torch.dot(embedding, centroid).item()
            
            if sim_centroid >= config.CENTROID_THRESHOLD:
                if sim_centroid > best_similarity:
                    best_name = name
                    best_similarity = sim_centroid
            else:
                # Step 2: Individual matching (fallback)
                sim_individuals = torch.matmul(individuals, embedding) # Shape: (N,)
                max_sim_idx = torch.argmax(sim_individuals).item()
                sim_indiv = sim_individuals[max_sim_idx].item()
                
                if sim_indiv >= config.INDIVIDUAL_THRESHOLD:
                    if sim_indiv > best_similarity:
                        best_name = name
                        best_similarity = sim_indiv
                        
        # Map similarity (-1.0 to 1.0) to a clean percentage (0.0 to 100.0)
        confidence = max(0.0, best_similarity) * 100.0
        
        return best_name, confidence
        
    def grant_access(self, name, confidence):
        """
        Abstraction function for granted access. Easy to hook up additional relay actuators here.
        """
        print(f"[ACCESS GRANTED] Welcome, {name}! (Confidence: {confidence:.1f}%)")

    def deny_access(self, frame):
        """
        Abstraction function for denied access. Handles throttled logging to prevent flood.
        """
        print("[ACCESS DENIED] Access denied: Unknown face.")
        
        current_time = time.time()
        # Throttling to save at most 1 snapshot per 5 seconds of continuous detection
        if current_time - self.last_unknown_log_time >= config.UNKNOWN_LOG_COOLDOWN:
            self.last_unknown_log_time = current_time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(config.LOGS_DIR, f"unknown_{timestamp}.jpg")
            cv2.imwrite(filename, frame)
            print(f"[LOGGING] Snapshot of unauthorized access saved to: {filename}")

    def log_access_event(self, name, result, signal_sent_status):
        """
        Records the access event to access_log.csv with a timestamp.
        """
        file_exists = os.path.exists(config.ACCESS_LOG_PATH)
        
        try:
            with open(config.ACCESS_LOG_PATH, mode="a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    # Write header
                    writer.writerow(["Timestamp", "Name", "Result", "SignalSent"])
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([timestamp, name, result, signal_sent_status])
        except Exception as e:
            print(f"[ENGINE] [ERROR] Failed to write event to access_log.csv: {e}")
