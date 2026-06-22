import cv2

class CameraStream:
    def __init__(self, src=0):
        """
        Dynamically detects the platform and camera hardware.
        Uses Picamera2 for Raspberry Pi CSI camera module if available,
        otherwise falls back to standard OpenCV cv2.VideoCapture (for USB webcams/PCs).
        """
        self.src = src
        self.is_pi_cam = False
        self.cap = None
        self.picam2 = None
        
        # Try importing picamera2 to detect if running on a Raspberry Pi with CSI Camera
        try:
            from picamera2 import Picamera2
            # We only use Picamera2 if accessing the default CSI camera (src=0)
            if src == 0:
                print("[CAMERA] Raspberry Pi Picamera2 library detected. Initializing CSI Camera Module...")
                self.picam2 = Picamera2()
                # Create a preview configuration (RGB format, 640x480)
                config = self.picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)})
                self.picam2.configure(config)
                self.picam2.start()
                self.is_pi_cam = True
                print("[CAMERA] [SUCCESS] Raspberry Pi CSI Camera Module initialized.")
        except (ImportError, Exception):
            # Fall back to standard OpenCV VideoCapture
            pass
            
        if not self.is_pi_cam:
            print(f"[CAMERA] Initializing standard OpenCV VideoCapture on source {src}...")
            self.cap = cv2.VideoCapture(src)
            # Set resolution properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def read(self):
        """
        Reads a frame from the active camera interface.
        Returns:
            ret: bool, True if capture succeeded, False otherwise
            frame: numpy array (BGR format) of the captured image
        """
        if self.is_pi_cam:
            try:
                frame = self.picam2.capture_array()
                # Picamera2 returns frames in RGB format; convert to BGR for OpenCV consistency
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame_bgr
            except Exception as e:
                print(f"[CAMERA] [ERROR] Failed to capture frame from Picamera2: {e}")
                return False, None
        else:
            if self.cap:
                return self.cap.read()
            return False, None

    def isOpened(self):
        """
        Checks if the camera interface was opened successfully.
        """
        if self.is_pi_cam:
            return self.picam2 is not None
        return self.cap is not None and self.cap.isOpened()

    def release(self):
        """
        Releases the camera resources.
        """
        if self.is_pi_cam:
            if self.picam2:
                try:
                    self.picam2.stop()
                    print("[CAMERA] Picamera2 resources released.")
                except Exception:
                    pass
                self.picam2 = None
        else:
            if self.cap:
                self.cap.release()
                print("[CAMERA] VideoCapture resources released.")
                self.cap = None
