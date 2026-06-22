/*
  ESP32 Wi-Fi Access Control Lock Firmware
  Controls a servo motor acting as a lock mechanism.
  Connects to Wi-Fi and hosts a local web server.
  
  Endpoints:
    http://<ESP32_IP>/handshake -> Responds "ACK" (self-test check)
    http://<ESP32_IP>/unlock    -> Drives servo to open angle, starts non-blocking timer, responds "UNLOCKED"
    http://<ESP32_IP>/lock      -> Drives servo to closed angle immediately, responds "LOCKED"

  Note: 
    1. Enter your Wi-Fi SSID and Password below before uploading.
    2. Requires the "ESP32Servo" library in the Arduino IDE.
*/

#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>

// --- WI-FI CREDENTIALS ---
// Set these to match your router settings (must match config.py in Python)
const char* ssid = "NARZO 70 Pro 5G";
const char* password = "Thush@r0308";

// --- CONFIGURABLE CONSTANTS ---
const int SERVO_PIN = 32;        // GPIO pin connected to the servo signal (D32 / GPIO 32 on ESP32)
const int OPEN_ANGLE = 90;       // Angle representing unlocked state (degrees)
const int CLOSE_ANGLE = 0;       // Angle representing locked state (degrees)
const unsigned long UNLOCK_DURATION = 3000; // Duration to remain unlocked (milliseconds)
const long BAUD_RATE = 9600;     // Serial communication speed for startup debugging

// --- STATE VARIABLES ---
Servo lockServo;
WebServer server(80); // Web server on port 80
bool isUnlocked = false;
unsigned long unlockStartTime = 0;

// --- HTTP ENDPOINT HANDLERS ---

void handleHandshake() {
  server.send(200, "text/plain", "ACK");
  Serial.println("[HTTP] Handshake request received.");
}

void handleUnlock() {
  lockServo.write(OPEN_ANGLE);
  isUnlocked = true;
  unlockStartTime = millis();
  server.send(200, "text/plain", "UNLOCKED");
  Serial.println("[HTTP] Unlock command triggered.");
}

void handleLock() {
  lockServo.write(CLOSE_ANGLE);
  isUnlocked = false;
  server.send(200, "text/plain", "LOCKED");
  Serial.println("[HTTP] Lock command triggered.");
}

void handleNotFound() {
  server.send(404, "text/plain", "Not Found");
}

void setup() {
  // Initialize Serial for console output (to display IP address)
  Serial.begin(BAUD_RATE);
  delay(500);
  
  // Allow allocation of all ESP32 PWM timers for servo control
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  
  // Attach and initialize servo to locked position
  lockServo.setPeriodHertz(50);           // Standard 50Hz servo refresh rate
  lockServo.attach(SERVO_PIN, 500, 2400); // Standard min/max pulse width for SG90 servo
  lockServo.write(CLOSE_ANGLE);
  
  // Connect to Wi-Fi
  Serial.println();
  Serial.print("[WIFI] Connecting to ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  // Wait for connection
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("");
    Serial.println("[WIFI] Connection successful!");
    Serial.print("[WIFI] ESP32 Local IP Address: ");
    Serial.println(WiFi.localIP()); // COPY THIS IP ADDRESS TO config.py
  } else {
    Serial.println("");
    Serial.println("[WIFI] [ERROR] Connection failed. Check credentials or router.");
  }
  
  // Configure Web Server routes
  server.on("/handshake", handleHandshake);
  server.on("/unlock", handleUnlock);
  server.on("/lock", handleLock);
  server.onNotFound(handleNotFound);
  
  // Start Web Server
  server.begin();
  Serial.println("[HTTP] Local Web Server started on port 80.");
}

void loop() {
  // Handle client requests
  server.handleClient();
  
  unsigned long currentTime = millis();
  
  // Non-blocking Auto-Lock Timer:
  // If the lock is open and the unlock duration has elapsed, lock it.
  if (isUnlocked && (currentTime - unlockStartTime >= UNLOCK_DURATION)) {
    lockServo.write(CLOSE_ANGLE);
    isUnlocked = false;
    Serial.println("[TIMER] Auto-locked.");
  }
}
