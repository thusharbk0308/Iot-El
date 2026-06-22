import os
import cv2
import time
import torch
import config
from face_engine import FaceEngine
from lock_controller import LockController
from camera_stream import CameraStream

def compute_iou(boxA, boxB):
    """
    Computes Intersection over Union (IoU) of two bounding boxes.
    Bounding box format: [x1, y1, x2, y2]
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    
    interArea = max(0, xB - xA) * max(0, yB - yA)
    
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    
    unionArea = boxAArea + boxBArea - interArea
    if unionArea == 0:
        return 0.0
        
    return interArea / float(unionArea)

def main():
    print("=== Real-time Face Recognition System (Lock Integration) ===")
    
    # 1. Load Face Database
    if not os.path.exists(config.DB_PATH):
        print(f"[ERROR] Database file not found at: {config.DB_PATH}")
        print("[INFO] Please register users and run 'python enroll.py' before running recognition.")
        return
        
    print(f"[INFO] Loading authorized face database...")
    try:
        database = torch.load(config.DB_PATH)
        print(f"[INFO] Successfully loaded {len(database)} enrolled user(s): {list(database.keys())}")
    except Exception as e:
        print(f"[ERROR] Failed to load database: {e}")
        return
        
    # 2. Initialize Hardware Lock Controller
    lock = LockController(port=config.ARDUINO_PORT, baudrate=config.BAUD_RATE)
    hardware_active = False
    
    if lock.connect():
        # Perform startup self-test check
        if lock.self_test():
            print("[INFO] Hardware Mode active: Lock controller connection confirmed.")
            hardware_active = True
        else:
            print("[WARNING] Lock failed startup self-test. Running in Software-Only mode.")
            lock.close()
    else:
        print("[INFO] Running in Software-Only mode.")
        
    # 3. Initialize Face Engine
    engine = FaceEngine()
    
    # 4. Open Camera Stream
    print("[INFO] Starting camera stream...")
    cap = CameraStream(0)
    if not cap.isOpened():
        print("[ERROR] Could not open camera. Please verify connection and permissions.")
        if hardware_active:
            lock.close()
        return
    
    # Tracker & Hardware state
    active_tracks = []
    last_unlock_time = 0.0
    
    print("\n[SUCCESS] System active. Press 'q' on the feed window to quit.")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Failed to read frame from camera.")
                break
                
            current_time = time.time()
            
            # Non-blocking check for any acknowledgements (applicable in SERIAL mode)
            if hardware_active:
                lock.check_responses()
                if not lock.connected:
                    hardware_active = False
                    print("[HARDWARE] Connection to lock controller lost. Falling back to Software-Only mode.")
                
            # Detect faces in the current frame
            boxes, probs = engine.detect_faces(frame)
            
            # Mark all existing tracks as not updated for this frame
            for track in active_tracks:
                track['updated'] = False
                
            if boxes is not None:
                # Match detected boxes with active tracks greedily based on IoU
                for box in boxes:
                    best_iou = -1.0
                    best_track = None
                    
                    for track in active_tracks:
                        if not track['updated']:
                            iou = compute_iou(box, track['box'])
                            if iou > best_iou:
                                best_iou = iou
                                best_track = track
                                
                    # If a match is found above IoU threshold (0.45)
                    if best_track is not None and best_iou >= 0.45:
                        best_track['updated'] = True
                        # Check cache age
                        time_elapsed = current_time - best_track['last_calc_time']
                        
                        if time_elapsed < config.CACHE_LIFETIME:
                            # CACHE HIT: Reuse classification results, update bounding box
                            best_track['box'] = box
                        else:
                            # CACHE EXPIRED: Run detection and classification again
                            h, w, _ = frame.shape
                            x1 = max(0, int(box[0]))
                            y1 = max(0, int(box[1]))
                            x2 = min(w, int(box[2]))
                            y2 = min(h, int(box[3]))
                            
                            if x2 - x1 >= 10 and y2 - y1 >= 10:
                                face_crop = frame[y1:y2, x1:x2]
                                try:
                                    name, confidence = engine.compare_embeddings(
                                        engine.get_embedding(face_crop), database
                                    )
                                    
                                    # Handle access triggers
                                    if name != "Unknown":
                                        signal_sent = "No (Cooldown Active)"
                                        # Check unlock cooldown
                                        if current_time - last_unlock_time >= config.UNLOCK_COOLDOWN:
                                            if hardware_active and lock.open_lock():
                                                last_unlock_time = current_time
                                                signal_sent = "Yes"
                                                print(f"[ACCESS] Triggered lock unlock for {name}.")
                                            elif hardware_active:
                                                signal_sent = "Failed"
                                                print("[WARNING] Failed to send open command to lock controller.")
                                                if not lock.connected:
                                                    hardware_active = False
                                                    print("[HARDWARE] Connection to lock controller lost. Falling back to Software-Only mode.")
                                            else:
                                                signal_sent = "No (Software-Only Mode)"
                                                
                                        engine.grant_access(name, confidence)
                                        engine.log_access_event(name, "Granted", signal_sent)
                                    else:
                                        engine.deny_access(frame)
                                        engine.log_access_event("Unknown", "Denied", "No")
                                        
                                    # Update track properties
                                    best_track['name'] = name
                                    best_track['confidence'] = confidence
                                    best_track['last_calc_time'] = current_time
                                except Exception as e:
                                    print(f"[ERROR] Inference error on cache update: {e}")
                            best_track['box'] = box
                    else:
                        # NEW FACE: Create a new track
                        h, w, _ = frame.shape
                        x1 = max(0, int(box[0]))
                        y1 = max(0, int(box[1]))
                        x2 = min(w, int(box[2]))
                        y2 = min(h, int(box[3]))
                        
                        if x2 - x1 >= 10 and y2 - y1 >= 10:
                            face_crop = frame[y1:y2, x1:x2]
                            try:
                                name, confidence = engine.compare_embeddings(
                                    engine.get_embedding(face_crop), database
                                )
                                
                                # Handle access triggers
                                if name != "Unknown":
                                    signal_sent = "No (Cooldown Active)"
                                    if current_time - last_unlock_time >= config.UNLOCK_COOLDOWN:
                                        if hardware_active and lock.open_lock():
                                            last_unlock_time = current_time
                                            signal_sent = "Yes"
                                            print(f"[ACCESS] Triggered lock unlock for {name}.")
                                        elif hardware_active:
                                            signal_sent = "Failed"
                                            print("[WARNING] Failed to send open command to lock controller.")
                                            if not lock.connected:
                                                hardware_active = False
                                                print("[HARDWARE] Connection to lock controller lost. Falling back to Software-Only mode.")
                                        else:
                                            signal_sent = "No (Software-Only Mode)"
                                            
                                    engine.grant_access(name, confidence)
                                    engine.log_access_event(name, "Granted", signal_sent)
                                else:
                                    engine.deny_access(frame)
                                    engine.log_access_event("Unknown", "Denied", "No")
                                    
                                new_track = {
                                    'box': box,
                                    'name': name,
                                    'confidence': confidence,
                                    'last_calc_time': current_time,
                                    'updated': True
                                }
                                active_tracks.append(new_track)
                            except Exception as e:
                                print(f"[ERROR] Inference error on new track: {e}")
                                
            # Clean up lost tracks (faces that left the frame)
            active_tracks = [t for t in active_tracks if t['updated']]
            
            # Visual Rendering: Draw bounding boxes and labels
            for track in active_tracks:
                x1, y1, x2, y2 = map(int, track['box'])
                name = track['name']
                confidence = track['confidence']
                
                if name != "Unknown":
                    color = (0, 255, 0) # Green for authorized
                    label = f"Access Granted: {name} ({confidence:.1f}%)"
                else:
                    color = (0, 0, 255) # Red for unauthorized
                    label = "Access Denied: Unknown"
                    
                # Draw face box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Draw label box background
                (w_txt, h_txt), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(frame, (x1, y1 - h_txt - 10), (x1 + w_txt + 10, y1), color, -1)
                
                # Draw label text
                cv2.putText(
                    frame, label, (x1 + 5, y1 - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA
                )
                
            # Draw status info on top of video feed
            status_line = f"Tracks: {len(active_tracks)} | Mode: {lock.mode} ({'ACTIVE' if hardware_active else 'SOFTWARE-ONLY'})"
            cv2.putText(
                frame, status_line, (10, 25), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1, cv2.LINE_AA
            )
            
            cv2.imshow("Real-Time Face Recognition Access Control", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        # 5. Clean teardown on exit
        cap.release()
        cv2.destroyAllWindows()
        if hardware_active and lock.connected:
            # Send an explicit Lock command on shutdown to ensure door locks
            print("[INFO] Shutting down. Locking hardware...")
            lock.close_lock()
            lock.close()
        elif lock.serial and lock.serial.is_open:
            lock.close()
        print("[INFO] Camera stream terminated. Goodbye.")

if __name__ == "__main__":
    main()
