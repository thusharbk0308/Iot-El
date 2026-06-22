# Face Recognition Access Control System: System Architecture & Technical Documentation

This document provides a detailed overview of how the real-time face recognition access control system is engineered, the tools used, and the programming techniques applied to achieve high CPU efficiency and reliable hardware integration.

---

## 🏗️ 1. System Architecture & Design Patterns

The codebase is built following a **modular, decoupled architecture** to separate core computations, hardware drivers, configurations, and user interfaces. 

```
┌────────────────────────────────────────────────────────────────────────┐
│                              config.py                                 │
│                   (Centralized Settings & Tuning)                      │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│          face_engine.py              │  │    arduino_controller.py     │
│  (AI Models, Preprocessing, Logs)    │  │ (HTTP Asynchronous / Serial) │
└───────────────────┬──────────────────┘  └──────────┬───────────────────┘
                    │                                │
                    └────────────────┬───────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                             recognize.py                               │
│                   (Main Orchestrator & OpenCV UI)                      │
└────────────────────────────────────────────────────────────────────────┘
```

### File Breakdown:
- **`config.py`**: Centralized configurations. Stores all math thresholds, cache lifetimes, Wi-Fi credentials, and file paths.
- **`arduino_controller.py`**: Hardware abstraction layer. Interfaces with the ESP32 wirelessly (via HTTP) or over a USB cable (via PySerial).
- **`face_engine.py`**: Artificial Intelligence layer. Handles MTCNN face detection, FaceNet embedding calculations, and database comparisons.
- **`recognize.py`**: Main application logic. Orchestrates webcam acquisition, runs face tracking, checks caches, triggers access decisions, and overlays status text on the screen.

---

## 🛠️ 2. Core Libraries & AI Models (The Tools)

### A. Deep Learning & Computer Vision
1. **PyTorch & Torchvision**: 
   The core deep learning framework. Handles tensor operations and feeds the face images to the neural networks.
2. **MTCNN (Multi-task Cascaded Convolutional Networks)**: 
   A cascading convolutional neural network comprising three sub-networks (P-Net, R-Net, O-Net). MTCNN:
   - Detects face bounding boxes.
   - Extracts 5 facial landmarks (eyes, nose, mouth corners) to align the face, ensuring high matching accuracy even if the person tilts their head.
3. **InceptionResnetV1 (FaceNet)**: 
   Pre-trained on the **VGGFace2** dataset. It extracts a **512-dimensional facial embedding vector** (facial fingerprint). The network is trained using triplet loss, ensuring that embeddings of the same person are clustered close together in 512D space.
4. **OpenCV-Python (`cv2`)**: 
   Handles raw video capture from the laptop webcam, downscaling frames, drawing box overlays, and writing logs.

### B. Networking & Communication
1. **Requests**: Standard Python library for sending HTTP GET requests (like `/unlock`, `/lock`, or `/handshake`) to the ESP32.
2. **PySerial**: Handles USB serial communications over virtual COM ports when running the system in legacy Serial mode.
3. **ESP32 WebServer & ESP32Servo (C++)**: C++ libraries running on the ESP32 microcontroller to route wireless HTTP requests and control the servo motor.

---

## ⚡ 3. Software Engineering Techniques (The Methods)

To enable real-time execution on a standard laptop CPU (without requiring an expensive GPU), we applied several optimization techniques:

### A. Face Tracking & Classification Caching (CPU Optimizer)
Running FaceNet embedding extraction on every webcam frame is computationally heavy and causes major lag on standard laptop CPUs.
* **The Optimization**: Bounding box tracking.
* **The Technique**:
  1. MTCNN runs on every frame to detect face coordinates.
  2. The system tracks faces frame-to-frame by calculating their **Intersection over Union (IoU)**.
  3. If a face box significantly overlaps with a tracked box (IoU $\ge 0.45$) and was classified less than **1.0 second** ago, the system **bypasses FaceNet embedding extraction completely**.
  4. The screen immediately displays the cached identity, maintaining a smooth ~30 FPS feed instead of dropping to ~3 FPS.

### B. Asynchronous HTTP Requests
Network requests over Wi-Fi can suffer from latency spikes. If Python waited synchronously for the ESP32 to respond, the video feed would freeze.
* **The Technique**: Background execution threads.
  ```python
  import threading
  threading.Thread(target=_async_http_request, args=(url, "Unlock"), daemon=True).start()
  ```
* **The Result**: Commands are sent in a separate background thread. The webcam feed remains completely responsive at maximum frame rate.

### C. Dual-Stage Matching (Centroid + Fallback)
To handle changes in expression, lighting, or accessories, we use a two-stage verification process:
- **Stage 1 (Primary - Centroid)**: Computes the average vector (centroid) of the user's 30 enrollment photos. When matching, we calculate the **Cosine Similarity** (dot product of L2-normalized vectors). If the score is $\ge 0.65$, access is granted.
- **Stage 2 (Secondary - Fallback)**: If the centroid check fails, it compares the input embedding against all 30 **individual embeddings** from the dataset. If any individual photo scores $\ge 0.60$, access is granted. This captures profiles or smiles that might differ from the mathematical average.

### D. Throttling and Event Logging
- **Access Logs**: Access events (`Timestamp, Name, Result, SignalSent`) are saved to `access_log.csv` dynamically.
- **Snapshots**: Snapshot images of unknown faces are written to `logs/`. The system enforces a **5-second throttling cooldown** to prevent flooding your hard drive with write operations.

---

## 🔌 4. Hardware State Machine Strategy

Traditional microcontroller code uses `delay(3000)` to hold the servo open. However, `delay()` is a **blocking** function—while delaying, the ESP32 cannot handle incoming HTTP requests.
* **The Technique**: Non-blocking timers using `millis()`.
* **The Code**:
  ```cpp
  if (isUnlocked && (currentTime - unlockStartTime >= UNLOCK_DURATION)) {
      lockServo.write(CLOSE_ANGLE);
      isUnlocked = false;
      Serial.println("LOCKED");
  }
  ```
* **The Result**: The ESP32 loop runs continuously. The timer checks are checked on every iteration, leaving the web server free to process incoming overrides (like explicit locking) at any moment.

### E. Graceful Connection Recovery
- **Self-Test Handshake**: On startup, Python sends a handshake (`'H'`) over the connection. The ESP32 replies with `'A'` (Acknowledged).
- **Graceful Fallback**: If the ESP32 loses connection, the controller catches the connection write error, logs a warning, and disables hardware mode. The system automatically degrades to **Software-Only mode**, keeping the camera feed active.
