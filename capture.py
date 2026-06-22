import os
import cv2
import time
from face_engine import FaceEngine
from camera_stream import CameraStream

def main():
    print("=== Face Dataset Capture Utility ===")
    name = input("Enter the name of the person to enroll: ").strip()
    if not name:
        print("[ERROR] Name cannot be empty. Exiting.")
        return
    
    # Sanitize name for directory creation
    safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c in (" ", "_", "-")]).strip()
    safe_name = safe_name.replace(" ", "_")
    
    output_dir = os.path.join("dataset", safe_name)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"[INFO] Initializing face detector...")
    engine = FaceEngine()
    
    print(f"[INFO] Opening camera stream...")
    cap = CameraStream(0)
    if not cap.isOpened():
        print("[ERROR] Could not open camera. Ensure it is connected and not in use by another app.")
        return
    
    print("\n--- INSTRUCTIONS ---")
    print("1. Stand in front of the camera in a well-lit environment.")
    print("2. The system will automatically capture a face when detected.")
    print("3. Tilt, turn, smile, or change angles slightly during capture.")
    print("4. Press 'q' to cancel and exit.")
    print("Press any key to start...")
    input()
    
    count = 0
    max_images = 30
    last_capture_time = 0.0
    capture_cooldown = 0.25 # seconds between automated captures (to allow user to change angles)
    
    print("[INFO] Starting capture loop. Press 'q' on the camera window to abort.")
    
    while count < max_images:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to read frame from webcam.")
            break
            
        # Create a display copy so we don't draw bounding boxes on the saved dataset images
        display_frame = frame.copy()
        
        # Detect face
        boxes, probs = engine.detect_faces(frame)
        
        current_time = time.time()
        face_detected = boxes is not None and len(boxes) > 0
        
        if face_detected:
            # We will only save the first detected face if multiple are present
            box = boxes[0]
            prob = probs[0]
            
            x1, y1, x2, y2 = map(int, box)
            # Draw green bounding box around the detected face
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Check capture cooldown
            if current_time - last_capture_time >= capture_cooldown:
                # Save the raw frame image (no bounding box) to dataset
                img_filename = os.path.join(output_dir, f"face_{count + 1:03d}.jpg")
                cv2.imwrite(img_filename, frame)
                
                last_capture_time = current_time
                count += 1
                print(f"[CAPTURE] Saved {count}/{max_images}: {img_filename}")
                
        # Draw UI overlay
        # Header bar
        cv2.rectangle(display_frame, (0, 0), (640, 50), (0, 0, 0), -1)
        status_text = f"User: {name} | Captured: {count}/{max_images}"
        cv2.putText(display_frame, status_text, (15, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Bottom guide bar
        cv2.rectangle(display_frame, (0, 430), (640, 480), (0, 0, 0), -1)
        if face_detected:
            guide_text = "Face detected! Tilt/smile for variety."
            text_color = (0, 255, 0)
        else:
            guide_text = "Align your face in the frame."
            text_color = (0, 0, 255)
        cv2.putText(display_frame, guide_text, (15, 462), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 1)
        
        # Show visual feed
        cv2.imshow("Dataset Capture Tool", display_frame)
        
        # Break on 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[INFO] Capture cancelled by user.")
            break
            
    cap.release()
    cv2.destroyAllWindows()
    
    if count == max_images:
        print(f"\n[SUCCESS] Successfully captured {max_images} images for {name}!")
        print(f"[INFO] Images are saved in: {output_dir}")
        print("[INFO] Next step: Run 'python enroll.py' to process embeddings.")
    else:
        print(f"\n[WARNING] Only captured {count}/{max_images} images. Consider running again to get a full dataset.")

if __name__ == "__main__":
    main()
