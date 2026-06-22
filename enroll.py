import os
import cv2
import torch
from tqdm import tqdm
from face_engine import FaceEngine

def main():
    print("=== Face Enrollment Processing ===")
    
    # Check if dataset directory exists and contains user folders
    dataset_dir = "dataset"
    if not os.path.exists(dataset_dir) or len(os.listdir(dataset_dir)) == 0:
        print("[ERROR] The 'dataset/' directory is empty or does not exist.")
        print("[INFO] Please run 'python capture.py' first to capture photos of authorized people.")
        return
        
    # Initialize the FaceEngine
    print("[INFO] Initializing FaceEngine...")
    engine = FaceEngine()
    
    database = {}
    
    # Iterate through all subdirectories in dataset/
    person_dirs = [d for d in os.listdir(dataset_dir) if os.path.isdir(os.path.join(dataset_dir, d))]
    
    if not person_dirs:
        print("[ERROR] No subdirectories (representing people) found in 'dataset/'.")
        print("[INFO] Please make sure user folders exist (e.g. 'dataset/Person1/').")
        return
        
    print(f"[INFO] Found {len(person_dirs)} user directories to enroll: {person_dirs}")
    
    for person_name in person_dirs:
        person_path = os.path.join(dataset_dir, person_name)
        image_files = [f for f in os.listdir(person_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        if not image_files:
            print(f"[WARNING] No images found in directory: {person_path}. Skipping.")
            continue
            
        print(f"\n[PROCESSING] Enrolling '{person_name}' using {len(image_files)} images...")
        embeddings_list = []
        
        for img_name in tqdm(image_files, desc=f"Processing {person_name}"):
            img_path = os.path.join(person_path, img_name)
            
            # Read image
            frame = cv2.imread(img_path)
            if frame is None:
                print(f"\n[WARNING] Could not read image: {img_path}. Skipping.")
                continue
                
            # Detect face
            boxes, probs = engine.detect_faces(frame)
            
            if boxes is not None and len(boxes) > 0:
                # Use the first/most confident face detected
                box = boxes[0]
                
                # Bounding box bounds check
                h, w, _ = frame.shape
                x1 = max(0, int(box[0]))
                y1 = max(0, int(box[1]))
                x2 = min(w, int(box[2]))
                y2 = min(h, int(box[3]))
                
                # Check for invalid crops
                if x2 - x1 < 10 or y2 - y1 < 10:
                    continue
                    
                face_crop = frame[y1:y2, x1:x2]
                
                try:
                    # Get embedding
                    embedding = engine.get_embedding(face_crop)
                    embeddings_list.append(embedding)
                except Exception as e:
                    print(f"\n[ERROR] Failed to extract embedding for {img_name}: {e}")
                    
        if len(embeddings_list) == 0:
            print(f"[WARNING] No faces could be processed for '{person_name}'. Skipping registration.")
            continue
            
        # Compute centroid (average embedding)
        embeddings_tensor = torch.stack(embeddings_list) # Shape: (N, 512)
        centroid = torch.mean(embeddings_tensor, dim=0)   # Shape: (512,)
        # L2-normalize the centroid
        centroid = centroid / centroid.norm()
        
        # Save centroid and individual embeddings
        database[person_name] = {
            "centroid": centroid,
            "individuals": embeddings_tensor
        }
        print(f"[SUCCESS] Enrolled '{person_name}' with {len(embeddings_list)} valid face embeddings.")
        
    if database:
        # Create embeddings directory if not exists
        os.makedirs("embeddings", exist_ok=True)
        db_path = os.path.join("embeddings", "authorized_faces.pt")
        
        print(f"\n[INFO] Saving embeddings database to: {db_path}")
        torch.save(database, db_path)
        print("[SUCCESS] Face enrollment completed successfully! You can now run 'python recognize.py'.")
    else:
        print("\n[ERROR] No users were successfully enrolled. Please check your dataset images.")

if __name__ == "__main__":
    main()
