# Raspberry Pi Migration & Hardware Setup Guide

This guide describes how to migrate the face recognition access control system from your laptop to a **Raspberry Pi** (Pi 4 or Pi 5) using the **Raspberry Pi Camera Module** (CSI ribbon interface) and an **ESP32** microcontroller.

---

## 🔌 1. Hardware Connections

```
      ┌──────────────────────┐               ┌────────────────┐
      │     Raspberry Pi     │               │  ESP32 Board   │
      │   (Runs Python App)  │               │ (Servo Driver) │
      │                      │               │                │
      │  [CSI Camera Port]   │               │                │
      │         │            │               │                │
      └─────────┼────────────┘               └────────┬───────┘
                │ (CSI Ribbon Cable)                  │
                ▼                                     │
      ┌──────────────────┐                            │
      │    Pi Camera     │                            │
      └──────────────────┘                            │
                                                      │
      - - - - - - - CONNECTION OPTION A: SERIAL - - - │ - - - -
      │                                               │       │
      │   [USB-A Port] <==================> [USB/COM]◄┘       │
      │                 (USB Cable)                           │
      - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
      
      - - - - - - - CONNECTION OPTION B: WI-FI - - - - - - - -
      │                                                       │
      │   [Wi-Fi Router] < - - (Wireless) - - > [Wi-Fi]       │
      │                                         (Powerbank)   │
      - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                                                      │
                                                      ▼
                                            ┌───────────────────┐
                                            │    Servo Motor    │
                                            │                   │
                                            │ Signal ➡️ Pin D22  │
                                            │ VCC    ➡️ 5V/VIN   │
                                            │ GND    ➡️ GND     │
                                            └───────────────────┘
```

### A. Connecting the Raspberry Pi Camera Module
1. Locate the **CSI Camera Port** on your Raspberry Pi:
   - **Pi 4**: Labeled `CAMERA`, between the audio jack and HDMI port.
   - **Pi 5**: Labeled `CAM/DISP 0` or `CAM/DISP 1` (Note: Pi 5 uses a smaller 22-pin connector, so you will need a Pi 5 specific camera cable).
2. Pull up the plastic collar on the port.
3. Insert the camera's ribbon cable with the metal contacts facing:
   - **Away** from the Ethernet port on Pi 4 (facing the HDMI ports).
   - **Toward** the board interior on Pi 5.
4. Push the plastic collar down to lock the cable in place.

### B. Connecting the ESP32 to the Raspberry Pi
You can choose either of the two connection options we built:

*   **Option A: USB Serial Cable (Wired)**:
    Simply plug the ESP32's micro-USB or USB-C cable into one of the Raspberry Pi's USB ports. 
    *Note: Our `arduino_controller.py` automatically detects Linux serial interfaces (like `/dev/ttyUSB0` or `/dev/ttyACM0`). You do not need to manually configure the COM port.*
*   **Option B: Local Wi-Fi (Wireless)**:
    Plug the ESP32 into a **power bank** for power. Ensure both the Raspberry Pi and the ESP32 are connected to the same Wi-Fi network. Configure the IP in `config.py` as detailed below.

---

## 💻 2. Software Setup on Raspberry Pi

Newer versions of Raspberry Pi OS (Debian Bullseye/Bookworm) enforce PEP-668, which blocks global `pip install` commands. We will set up a virtual environment that shares the Pi's pre-compiled system libraries.

### Step 1: Install System Packages
Run these commands in the terminal on your Raspberry Pi:
```bash
sudo apt update
sudo apt upgrade -y
# Install OpenCV and Picamera2 system libraries (faster than compiling from source)
sudo apt install -y python3-pip python3-opencv python3-picamera2
```

### Step 2: Create a Virtual Environment (Sharing System Packages)
Create a virtual environment that inherits the system packages. This allows our virtual environment to use the pre-compiled, hardware-accelerated Pi camera and OpenCV libraries:
```bash
# Navigate to the project folder
cd ~/face_recognition_system

# Create the virtual environment inheriting system site packages
python3 -m venv --system-site-packages venv

# Activate the virtual environment
source venv/bin/activate
```

### Step 3: Install Python Dependencies
With the virtual environment active (`(venv)` shown in your terminal prompt), run:
```bash
pip install --upgrade pip
pip install facenet-pytorch requests tqdm pyserial

# Install CPU version of PyTorch and torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

---

## ⚙️ 3. How the Cross-Platform Code Works

We added **`camera_stream.py`** to handle hardware differences. It wraps camera loading automatically:
- It attempts to import `picamera2`. 
- If found, it uses the official Raspberry Pi **`Picamera2`** library (configured to extract RGB frames and convert them to BGR NumPy arrays).
- If not found (e.g. running on Windows or utilizing a USB webcam on the Pi), it falls back to standard **`cv2.VideoCapture(0)`**.

### Configuration Check:
Open [config.py](file:///C:/Users/thush/.gemini/antigravity/scratch/face_recognition_system/config.py) and check your settings:
- **For Wi-Fi Mode**:
  ```python
  CONNECTION_MODE = "WIFI"
  ESP32_IP = "192.168.1.15" # Enter your ESP32's local IP address
  ```
- **For Wired USB Mode**:
  ```python
  CONNECTION_MODE = "SERIAL"
  ARDUINO_PORT = "AUTO"  # Will auto-detect /dev/ttyUSB0
  ```

---

## 🚀 4. Running the System on the Raspberry Pi

Ensure your virtual environment is active, then execute the commands:

1. **Test the Camera Stream & Enrollment** (if registering new faces on the Pi):
   ```bash
   python capture.py
   python enroll.py
   ```
2. **Start the Real-time Access Control Loop**:
   ```bash
   python recognize.py
   ```
   *Press **`q`** in the window to shut down the stream and safely lock the hardware.*
