# ==========================================
# Face Recognition Access Control Config
# ==========================================

# --- Connection Mode ---
# Options: "WIFI" or "SERIAL"
CONNECTION_MODE = "WIFI"

# --- Wi-Fi Credentials (Required for WIFI mode) ---
# Enter your local Wi-Fi router settings here.
# The ESP32 and your laptop must be connected to this same network.
WIFI_SSID = "NARZO 70 Pro 5G"
WIFI_PASSWORD = "Thush@r0308"

# --- ESP32 IP Address (Required for WIFI mode) ---
# Once the ESP32 boots up, it will print its IP address to the Serial Monitor.
# Copy that IP address here (e.g. "192.168.1.15").
ESP32_IP = "10.160.129.154"

# --- Serial Mode Configurations (Fallback) ---
ARDUINO_PORT = "AUTO"          # Port name (e.g. "COM3") or "AUTO" to scan ports
BAUD_RATE = 9600               # Serial communication baud rate

# --- Access Control Timing Parameters ---
UNLOCK_COOLDOWN = 5.0          # Seconds to wait before sending a new unlock command
UNKNOWN_LOG_COOLDOWN = 5.0     # Throttling time (seconds) between intruder logs in logs/

# --- Recognition Model Thresholds ---
# Cosine Similarity thresholds (0.0 to 1.0)
CENTROID_THRESHOLD = 0.65      # Stricter: Match against the user's average representation
INDIVIDUAL_THRESHOLD = 0.60    # Fallback: Match against individual dataset frames

# --- Performance Caches ---
CACHE_LIFETIME = 1.0           # Seconds to cache tracked face classifications

# --- File System Paths ---
DB_PATH = "embeddings/authorized_faces.pt"
LOGS_DIR = "logs"
ACCESS_LOG_PATH = "access_log.csv"
MODELS_DIR = "models"
