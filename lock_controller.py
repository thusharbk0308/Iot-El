import time
import threading
import requests
import serial
import serial.tools.list_ports
import config

def _async_http_request(url, label):
    """
    Helper function to send HTTP requests asynchronously in a background thread
    for WIFI mode, preventing any latency from blocking the video feed.
    """
    try:
        r = requests.get(url, timeout=2.0)
        if r.status_code == 200:
            print(f"[WIFI ACK] {label}: {r.text}")
        else:
            print(f"[WIFI WARNING] {label} returned code {r.status_code}")
    except Exception as e:
        print(f"[WIFI ERROR] Connection lost to ESP32: {e}")

class LockController:
    def __init__(self, port="AUTO", baudrate=9600):
        self.config_port = port
        self.baudrate = baudrate
        self.serial = None
        self.port = None
        self.connected = False
        self.mode = config.CONNECTION_MODE
        self.servo = None  # Used for direct Raspberry Pi GPIO mode

    def auto_detect_port(self):
        """
        Scans active ports for an ESP32/Arduino device (fallback for SERIAL mode).
        """
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            desc = p.description.lower()
            hwid = p.hwid.lower()
            manufacturer = (p.manufacturer or "").lower()
            
            keywords = ["arduino", "ch340", "usb serial", "usb-to-uart", "ftdi", "cp210", "prolific", "genuino"]
            if any(k in desc or k in hwid or k in manufacturer for k in keywords):
                print(f"[SERIAL] Auto-detected possible device on port: {p.device} ({p.description})")
                return p.device
                
        if ports:
            print(f"[SERIAL] Fallback to first available port: {ports[0].device}")
            return ports[0].device
            
        return None

    def connect(self):
        """
        Establishes a connection to the lock.
        Supports PI (GPIO), WIFI (HTTP), and SERIAL (USB).
        """
        if self.mode == "PI":
            print(f"[PI HW] Initializing servo on GPIO pin {config.PI_SERVO_PIN}...")
            try:
                # gpiozero is standard on Raspberry Pi OS
                from gpiozero import Servo
                # Set up the servo. We default to min() as locked.
                self.servo = Servo(config.PI_SERVO_PIN)
                self.servo.min()  # Initialize to locked position
                self.connected = True
                print(f"[PI HW] [SUCCESS] Servo initialized on Raspberry Pi GPIO {config.PI_SERVO_PIN}.")
                return True
            except ImportError:
                print("[PI HW] [WARNING] 'gpiozero' module not found. Running in Software-Only mode.")
                print("[PI HW] [INFO] (Note: 'gpiozero' is only available on Raspberry Pi devices).")
                self.connected = False
                return False
            except Exception as e:
                print(f"[PI HW] [ERROR] Failed to initialize Pi GPIO Servo: {e}")
                self.connected = False
                return False
                
        elif self.mode == "WIFI":
            print(f"[WIFI] Testing wireless connection to ESP32 at http://{config.ESP32_IP}/ ...")
            try:
                url = f"http://{config.ESP32_IP}/handshake"
                r = requests.get(url, timeout=3.0)
                if r.status_code == 200 and r.text.strip() == "ACK":
                    self.connected = True
                    print(f"[WIFI] [SUCCESS] Wireless connection verified. ESP32 is online.")
                    return True
                else:
                    print(f"[WIFI] [WARNING] Device responded, but handshake returned: '{r.text}'")
                    self.connected = False
                    return False
            except Exception as e:
                print(f"[WIFI] [ERROR] Failed to connect to ESP32 at {config.ESP32_IP}: {e}")
                self.connected = False
                return False
                
        else: # SERIAL Mode
            if self.config_port == "AUTO":
                self.port = self.auto_detect_port()
            else:
                self.port = self.config_port

            if not self.port:
                print("[SERIAL] [WARNING] No serial COM ports detected. Running in Software-Only mode.")
                self.connected = False
                return False

            try:
                print(f"[SERIAL] Opening serial connection on port {self.port} at {self.baudrate} baud...")
                self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
                time.sleep(2)  # Wait for bootloader reset
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()
                self.connected = True
                print(f"[SERIAL] [SUCCESS] Connection established on {self.port}.")
                return True
            except Exception as e:
                print(f"[SERIAL] [ERROR] Failed to open port {self.port}: {e}")
                self.connected = False
                self.serial = None
                return False

    def self_test(self):
        """
        Runs connection verification handshake.
        For PI mode, this runs a quick physical sweep test.
        """
        if not self.connected:
            return False

        if self.mode == "PI":
            if not self.servo:
                return False
            try:
                print("[PI HW] Running servo self-test sweep...")
                self.servo.max()  # Open
                time.sleep(0.5)
                self.servo.min()  # Lock
                print("[PI HW] [SUCCESS] Servo self-test completed.")
                return True
            except Exception as e:
                print(f"[PI HW] [ERROR] Self-test sweep failed: {e}")
                return False
                
        elif self.mode == "WIFI":
            return self.connected
            
        else: # SERIAL mode
            if not self.serial:
                return False
            try:
                print("[SERIAL] Running startup self-test handshake...")
                self.serial.write(b'H')
                self.serial.flush()
                response = self.serial.readline().decode().strip()
                if response == 'A':
                    print("[SERIAL] [SUCCESS] Handshake self-test passed! Device acknowledged.")
                    return True
                else:
                    print(f"[SERIAL] [WARNING] Handshake failed. Expected 'A', received: '{response}'")
                    return False
            except Exception as e:
                print(f"[SERIAL] [ERROR] Handshake failed: {e}")
                return False

    def open_lock(self):
        """
        Triggers unlock. Handles auto-locking timer in background for PI mode.
        """
        if not self.connected:
            return False

        if self.mode == "PI":
            if not self.servo:
                return False
            try:
                self.servo.max()  # Move servo to open angle
                print(f"[PI HW] Lock set to OPEN. Auto-locking in {config.UNLOCK_DURATION} seconds...")
                
                # Asynchronous thread to handle relocking automatically without blocking main thread
                def _auto_lock_timer():
                    time.sleep(config.UNLOCK_DURATION)
                    self.close_lock()
                    
                threading.Thread(target=_auto_lock_timer, daemon=True).start()
                return True
            except Exception as e:
                print(f"[PI HW] [ERROR] Failed to set open state: {e}")
                self.connected = False
                return False
                
        elif self.mode == "WIFI":
            url = f"http://{config.ESP32_IP}/unlock"
            threading.Thread(target=_async_http_request, args=(url, "Unlock"), daemon=True).start()
            return True
            
        else: # SERIAL Mode
            if not self.serial:
                return False
            try:
                self.serial.write(b'O')
                self.serial.flush()
                return True
            except Exception as e:
                print(f"[SERIAL] [ERROR] Connection lost during unlock write: {e}")
                self.connected = False
                return False

    def close_lock(self):
        """
        Triggers explicit lock command.
        """
        if not self.connected:
            return False

        if self.mode == "PI":
            if not self.servo:
                return False
            try:
                self.servo.min()  # Move servo to locked angle
                print("[PI HW] Lock set to LOCKED.")
                return True
            except Exception as e:
                print(f"[PI HW] [ERROR] Failed to set locked state: {e}")
                self.connected = False
                return False
                
        elif self.mode == "WIFI":
            url = f"http://{config.ESP32_IP}/lock"
            threading.Thread(target=_async_http_request, args=(url, "Lock"), daemon=True).start()
            return True
            
        else: # SERIAL Mode
            if not self.serial:
                return False
            try:
                self.serial.write(b'L')
                self.serial.flush()
                return True
            except Exception as e:
                print(f"[SERIAL] [ERROR] Connection lost during lock write: {e}")
                self.connected = False
                return False

    def check_responses(self):
        """
        Checks for incoming serial responses. (Only needed in SERIAL mode)
        """
        if self.mode != "SERIAL" or not self.connected or not self.serial:
            return
            
        try:
            if self.serial.in_waiting > 0:
                line = self.serial.readline().decode().strip()
                if line:
                    print(f"[SERIAL ACK] {line}")
        except Exception as e:
            print(f"[SERIAL] [WARNING] Connection lost during read: {e}")
            self.connected = False

    def close(self):
        """
        Closes connection resources.
        """
        if self.mode == "PI" and self.servo:
            try:
                # Release GPIO pin resources
                self.servo.close()
                print("[PI HW] Servo GPIO pin released.")
            except Exception:
                pass
            self.servo = None
            
        elif self.mode == "SERIAL" and self.serial and self.serial.is_open:
            try:
                self.serial.close()
                print("[SERIAL] Connection closed.")
            except Exception:
                pass
        self.connected = False
        self.serial = None
