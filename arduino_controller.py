import time
import threading
import requests
import serial
import serial.tools.list_ports
import config

def _async_http_request(url, label):
    """
    Helper function to send HTTP requests asynchronously in a background thread,
    preventing any latency or blocking of the main face recognition video feed.
    """
    try:
        r = requests.get(url, timeout=2.0)
        if r.status_code == 200:
            print(f"[WIFI ACK] {label}: {r.text}")
        else:
            print(f"[WIFI WARNING] {label} returned code {r.status_code}")
    except Exception as e:
        print(f"[WIFI ERROR] Connection lost to ESP32: {e}")

class ArduinoController:
    def __init__(self, port="AUTO", baudrate=9600):
        self.config_port = port
        self.baudrate = baudrate
        self.serial = None
        self.port = None
        self.connected = False
        self.mode = config.CONNECTION_MODE

    def auto_detect_port(self):
        """
        Scans active COM ports for an Arduino or general USB serial device (fallback).
        """
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            desc = p.description.lower()
            hwid = p.hwid.lower()
            manufacturer = (p.manufacturer or "").lower()
            
            keywords = ["arduino", "ch340", "usb serial", "usb-to-uart", "ftdi", "cp210", "prolific", "genuino"]
            if any(k in desc or k in hwid or k in manufacturer for k in keywords):
                print(f"[SERIAL] Auto-detected possible Arduino on port: {p.device} ({p.description})")
                return p.device
                
        if ports:
            print(f"[SERIAL] Fallback to first available port: {ports[0].device}")
            return ports[0].device
            
        return None

    def connect(self):
        """
        Establishes a connection to the ESP32.
        Supports both Wi-Fi (HTTP ping) and Serial modes.
        """
        if self.mode == "WIFI":
            print(f"[WIFI] Testing wireless connection to ESP32 at http://{config.ESP32_IP}/ ...")
            try:
                # Ping the handshake endpoint
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
                print("[WIFI] [INFO] Ensure ESP32 is powered and connected to the same Wi-Fi network.")
                self.connected = False
                return False
        else:
            # Fallback to SERIAL mode
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
                time.sleep(2) # Wait for ESP32 auto-reset
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
        """
        if self.mode == "WIFI":
            # Wi-Fi handshake is verified during connect()
            return self.connected
            
        # Serial mode handshake
        if not self.connected or not self.serial:
            return False
            
        try:
            print("[SERIAL] Running startup self-test handshake...")
            self.serial.write(b'H')
            self.serial.flush()
            response = self.serial.readline().decode().strip()
            if response == 'A':
                print("[SERIAL] [SUCCESS] Handshake self-test passed! Arduino acknowledged.")
                return True
            else:
                print(f"[SERIAL] [WARNING] Handshake failed. Expected 'A', received: '{response}'")
                return False
        except Exception as e:
            print(f"[SERIAL] [ERROR] Handshake failed: {e}")
            return False

    def open_lock(self):
        """
        Triggers unlock command.
        """
        if not self.connected:
            return False

        if self.mode == "WIFI":
            url = f"http://{config.ESP32_IP}/unlock"
            # Launch in background thread to prevent UI lag
            threading.Thread(target=_async_http_request, args=(url, "Unlock"), daemon=True).start()
            return True
        else:
            # Serial Mode
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

        if self.mode == "WIFI":
            url = f"http://{config.ESP32_IP}/lock"
            threading.Thread(target=_async_http_request, args=(url, "Lock"), daemon=True).start()
            return True
        else:
            # Serial Mode
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
        if self.mode == "WIFI" or not self.connected or not self.serial:
            return
            
        try:
            if self.serial.in_waiting > 0:
                line = self.serial.readline().decode().strip()
                if line:
                    print(f"[ARDUINO ACK] {line}")
        except Exception as e:
            print(f"[SERIAL] [WARNING] Connection lost during read: {e}")
            self.connected = False

    def close(self):
        """
        Closes connection resources.
        """
        if self.mode == "SERIAL" and self.serial and self.serial.is_open:
            try:
                self.serial.close()
                print("[SERIAL] Connection closed.")
            except Exception:
                pass
        self.connected = False
        self.serial = None
