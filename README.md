# Real-Time Face Recognition Access Control System (Arduino Integration)

A production-quality, CPU-optimized, real-time face recognition system in Python. It utilizes your laptop webcam to recognize registered individuals, dynamically tracks faces, and integrates with an Arduino Uno and a servo motor to control a physical lock mechanism.

---

## 🚀 Key Features
- **Arduino Uno Integration**: Interfaces with a physical servo motor lock mechanism.
- **Asynchronous, Non-Blocking Servo Control**: The Arduino firmware uses a state machine (`millis()`) instead of blocking delays, enabling instant overrides (like lock commands) and status logs.
- **Software-Only Graceful Fallback**: If the Arduino is disconnected or the COM port is busy, the script issues a warning and runs normally in software mode without crashing.
- **Auto-Port Detection**: Automatically scans for connected Arduino boards using hardware descriptors (including cheap clone drivers like CH340, CP210x, and FTDI).
- **Python Cooldown (5s)**: Enforces a 5-second cooldown on the Python side before sending repeat unlock commands, preventing servo wear.
- **Access Logging**: Logs every event to `access_log.csv` with columns: `Timestamp`, `Name`, `Result`, and `SignalSent`.
- **Intruder Logs (5s Cooldown)**: Saves timestamped snapshots of unrecognized faces under `logs/` (throttled to 1 image per 5 seconds).
- **Tracking Caching (1s)**: Leverages a bounding box tracker to cache identities for 1.0 second, reducing CPU usage by ~90%.
- **Centralized Settings**: All thresholds, timing intervals, and paths are defined in `config.py`.

---

## 📁 Project Structure
```
face_recognition_system/
│
├── dataset/                    # Face images per enrolled user (created by capture.py)
│
├── embeddings/                 # Compiled embeddings database
│   └── authorized_faces.pt
│
├── logs/                       # Folder for unauthorized access snapshots
│
├── models/                     # Cache folder for offline weights
│
├── arduino_lock/               # Arduino IDE project directory
│   └── arduino_lock.ino       # Non-blocking C++ sketch for Arduino Uno
│
├── config.py                   # Centralized configuration constants
├── arduino_controller.py       # Wrapper class for Arduino serial communications
├── face_engine.py              # Shared face detection, embedding, & logging
├── capture.py                  # CLI webcam photo capture tool
├── enroll.py                   # Script to convert datasets to centroids
├── recognize.py                # Main webcam loop with ArduinoController
├── access_log.csv              # CSV database of all access attempts
├── requirements.txt            # Project dependencies (includes pyserial)
└── README.md                   # This instruction guide
```

---

## 🔌 Hardware Setup & Wiring

### 1. Wiring Schematic
Connect your servo motor to the Arduino Uno as follows:
- **GND (Brown/Black)** ➡️ Arduino **GND**
- **VCC (Red)** ➡️ Arduino **5V**
- **Signal (Orange/Yellow)** ➡️ Arduino Digital Pin **9**

### 2. Upload the Firmware
1. Open the [arduino_lock.ino](file:///C:/Users/thush/.gemini/antigravity/scratch/face_recognition_system/arduino_lock/arduino_lock.ino) file in the Arduino IDE.
2. Select your board (**Arduino Uno**) and serial port in the IDE.
3. Click **Upload** to flash the code.
4. Close the Arduino Serial Monitor before running the Python script, as only one application can access the serial port at a time.

---

## 🛠️ Software Setup & Installation

Since PyTorch and torchvision are already installed on your system, setting up dependencies is instant:

1. **Open your terminal** and navigate to the project directory:
   ```powershell
   cd "C:\Users\thush\.gemini\antigravity\scratch\face_recognition_system"
   ```
2. **Install remaining packages**:
   ```powershell
   pip install -r requirements.txt
   ```

---

## ⚙️ Operation Workflow

### Step 1: Capture Face Data
```powershell
python capture.py
```
- Enter the person's name (e.g. `Alice`).
- The utility will auto-capture **30 images** once your face is detected.
- Tilt and turn your head slightly during capture to register variety.

### Step 2: Enroll Users
Process the captured images to generate embeddings:
```powershell
python enroll.py
```
- Computes the average vector (**centroid**) and lists of individual embeddings.
- Saves the database mapping to `embeddings/authorized_faces.pt`.

### Step 3: Run Live Recognition
Launch the real-time recognition and lock controller:
```powershell
python recognize.py
```
- The script automatically searches for your Arduino and runs a startup handshake self-test.
- If it connects, the top-left HUD will display `Hardware: ACTIVE`.
- If no Arduino is connected, it runs in software mode, showing `Hardware: SOFTWARE-ONLY`.
- Press **`q`** inside the webcam window to exit.

---

## 🛠️ Calibration & Customizations

Open [config.py](file:///C:/Users/thush/.gemini/antigravity/scratch/face_recognition_system/config.py) to edit these settings:

- **`CENTROID_THRESHOLD`**: Cosine similarity threshold for primary centroid match (default: `0.65`).
- **`INDIVIDUAL_THRESHOLD`**: Cosine similarity threshold for individual face match (default: `0.60`).
- **`CACHE_LIFETIME`**: Face tracking cache duration in seconds (default: `1.0`).
- **`UNLOCK_COOLDOWN`**: Wait time before sending another unlock signal to the servo (default: `5.0`).
- **`ARDUINO_PORT`**: Set to `"AUTO"` for auto-scanning, or hardcode your port (e.g. `"COM3"`).
- **`BAUD_RATE`**: Serial baud rate matching the Arduino speed (default: `9600`).
