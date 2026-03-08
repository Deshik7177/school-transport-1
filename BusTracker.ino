// BusTracker.ino - ESP32 School Bus Tracking System
// Pinout: RFID (SCK:18, MISO:19, MOSI:23, SS:15, RST:4), I2C MPU6050 (SDA:21, SCL:22), GPS Neo-6M (RX2:16, TX2:17)

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <MPU6050.h>
#include <EEPROM.h>
#include <TinyGPS++.h>
#include <ArduinoJson.h>
#include <WebServer.h>

// =======================
// WiFi Credentials
// =======================
const char* ssid = "Deshik";
const char* password = "129129129";

// =======================
// HiveMQ MQTT
// =======================


// =======================
// RFID Pins
// =======================
#define SS_PIN  15
#define RST_PIN 4
MFRC522 rfid(SS_PIN, RST_PIN);

// =======================
// MPU6050
// =======================
MPU6050 mpu;

// =======================
// GPS Neo-6M
// =======================
HardwareSerial SerialGPS(2); // UART2
TinyGPSPlus gps;
#define GPS_RX_PIN 16
#define GPS_TX_PIN 17

// =======================
// EEPROM Settings
// =======================
#define EEPROM_SIZE 1024
#define MAX_STUDENTS 10
#define UID_LENGTH 8
#define NAME_LENGTH 12

// =======================
// Student Data
// =======================
String studentUID[MAX_STUDENTS];
String studentName[MAX_STUDENTS];
bool insideStatus[MAX_STUDENTS];
int studentCount = 0;

// =======================
// Status Variables
// =======================
String accidentStatus = "Safe";
String rashStatus = "Driving Normal";

// =======================
// MPU Values
// =======================
float accX, accY, accZ;
float accMag;
float rollAngle = 0;
float pitchAngle = 0;
float gyroZValue = 0;

// =======================
// Thresholds
// =======================
float accidentThreshold = 2.8; // g-force
float tiltThreshold = 25.0;    // degrees
float sharpTurnThreshold = 200.0;
float accidentGyroThreshold = 450.0;

// =======================
// Function Prototypes
// =======================
void saveToEEPROM();
void loadFromEEPROM();
void setupWiFi();

void publishStatus();
void readRFID();
void readMPU();
void readGPS();

// =======================
// Declare server
// =======================
WebServer server(80);

// Declare missing variables
bool registerMode = false;
String tempName = "";
String modeStatus = "Attendance Mode";
String attendanceStatus = "No Activity";

// Missing function implementations
void registerStudent(String uid, String name) {
    // Implement registration logic here
}

int findStudent(String uid) {
    // Implement logic to find a student by UID
    return -1; // Return -1 if not found
}

String studentListHTML() {
    // Generate and return HTML for the student list
    return "<ul><li>Sample Student</li></ul>";
}

// =======================
// Setup
// =======================
void setup() {
  Serial.begin(115200);
  SerialGPS.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  SPI.begin();
  rfid.PCD_Init();
  Wire.begin(21, 22);
  mpu.initialize();
  EEPROM.begin(EEPROM_SIZE);
  loadFromEEPROM();
  setupWiFi();

  server.on("/data", handleData);   
  server.on("/register", handleRegister);
  server.begin();
}

// =======================
// Main Loop
// =======================
unsigned long lastPublish = 0;
void loop() {
  server.handleClient();

  // MPU6050 Reading
  int16_t ax, ay, az;
  int16_t gx, gy, gz;

  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

  float AccX = ax / 16384.0;
  float AccY = ay / 16384.0;
  float AccZ = az / 16384.0;

  gyroZValue = gz / 131.0;

  rollAngle = atan2(AccY, AccZ) * 57.3;
  pitchAngle = atan2(-AccX, sqrt(AccY * AccY + AccZ * AccZ)) * 57.3;

  float accelMag = sqrt(AccX * AccX + AccY * AccY + AccZ * AccZ);

  // Rash Driving Detection
  if (abs(rollAngle) > tiltThreshold ||
      abs(pitchAngle) > tiltThreshold ||
      abs(gyroZValue) > sharpTurnThreshold) {
    rashStatus = "⚠ Rash Driving Detected!";
  } else {
    rashStatus = "Driving Normal";
  }

  // Accident Detection
  if (accelMag > accidentThreshold || 
      abs(gyroZValue) > accidentGyroThreshold) {
    accidentStatus = "💥 Accident Detected!";
  } else {
    accidentStatus = "Safe";
  }

  // ...existing code...

  // RFID Scan
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {

    String uid = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
      uid += String(rfid.uid.uidByte[i], HEX);
    }
    uid.toUpperCase();

    if (registerMode) {
      registerStudent(uid, tempName);
      registerMode = false;
      modeStatus = "Attendance Mode";
    }
    else {
      int index = findStudent(uid);

      if (index == -1) {
        attendanceStatus = "Unknown Card!";
      } else {
        insideStatus[index] = !insideStatus[index];

        if (insideStatus[index])
          attendanceStatus = studentName[index] + " Boarded";
        else
          attendanceStatus = studentName[index] + " Dropped";

        saveToEEPROM();
      }
    }

    rfid.PICC_HaltA();
  }

  delay(200);
}

// =======================
// WiFi Setup
// =======================
void setupWiFi() {
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

// =======================
// MQTT Reconnect
// =======================


// =======================
// RFID Read
// =======================
void readRFID() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  int idx = -1;
  for (int i = 0; i < studentCount; i++) {
    if (studentUID[i] == uid) {
      idx = i;
      break;
    }
  }
  if (idx == -1 && studentCount < MAX_STUDENTS) {
    studentUID[studentCount] = uid;
    studentName[studentCount] = "Student" + String(studentCount + 1);
    insideStatus[studentCount] = true;
    studentCount++;
    saveToEEPROM();
  } else if (idx != -1) {
    insideStatus[idx] = !insideStatus[idx];
    saveToEEPROM();
  }
  rfid.PICC_HaltA();
}

// =======================
// MPU6050 Read
// =======================
void readMPU() {
  accX = mpu.getAccelerationX() / 16384.0;
  accY = mpu.getAccelerationY() / 16384.0;
  accZ = mpu.getAccelerationZ() / 16384.0;
  accMag = sqrt(accX * accX + accY * accY + accZ * accZ);

  rollAngle = atan2(accY, accZ) * 57.3;
  pitchAngle = atan2(-accX, sqrt(accY * accY + accZ * accZ)) * 57.3;
  gyroZValue = mpu.getRotationZ() / 131.0;

  // Rash driving logic
  if (abs(rollAngle) > tiltThreshold || abs(pitchAngle) > tiltThreshold || abs(gyroZValue) > sharpTurnThreshold) {
    rashStatus = "Rash Driving";
  } else {
    rashStatus = "Driving Normal";
  }

  // Accident detection
  if (accMag > accidentThreshold || abs(gyroZValue) > accidentGyroThreshold) {
    accidentStatus = "Accident Detected";
  } else {
    accidentStatus = "Safe";
  }
}

// =======================
// GPS Read
// =======================
float latitude = 0.0, longitude = 0.0, speedKmph = 0.0;
void readGPS() {
  while (SerialGPS.available() > 0) {
    gps.encode(SerialGPS.read());
  }
  if (gps.location.isValid()) {
    latitude = gps.location.lat();
    longitude = gps.location.lng();
  }
  if (gps.speed.isValid()) {
    speedKmph = gps.speed.kmph();
  }
}

// =======================
// Publish Status to MQTT
// =======================
void publishStatus() {
  String payload;
  DynamicJsonDocument doc(256);
  doc["lat"] = latitude;
  doc["lng"] = longitude;
  doc["speed"] = speedKmph;
  doc["safety"] = accidentStatus;
  doc["rash"] = rashStatus; // Include rash driving status
  doc["roll"] = rollAngle;
  doc["pitch"] = pitchAngle;
  doc["gyroZ"] = gyroZValue;
  doc["accMag"] = accMag;
  JsonArray onboard = doc.createNestedArray("students_onboard");
  for (int i = 0; i < studentCount; i++) {
    if (insideStatus[i]) onboard.add(studentUID[i]);
  }
  serializeJson(doc, payload);

  // Print JSON payload to Serial Monitor for debugging
  Serial.println("--- JSON Payload ---");
  Serial.println(payload);

  HTTPClient http;
  http.begin("http://172.24.180.1:5000/update"); // Updated to your PC's IP address
  http.addHeader("Content-Type", "application/json");
  int httpResponseCode = http.POST(payload);

  // Print HTTP response code to Serial Monitor for debugging
  Serial.print("HTTP Response code: ");
  Serial.println(httpResponseCode);

  http.end();
}

// =======================
// SAVE STUDENTS TO EEPROM
// =======================
void saveToEEPROM() {
  EEPROM.write(0, studentCount);
  int addr = 1;
  for (int i = 0; i < studentCount; i++) {
    for (int j = 0; j < UID_LENGTH; j++) {
      char c = (j < studentUID[i].length()) ? studentUID[i][j] : '\0';
      EEPROM.write(addr++, c);
    }
    for (int j = 0; j < NAME_LENGTH; j++) {
      char c = (j < studentName[i].length()) ? studentName[i][j] : '\0';
      EEPROM.write(addr++, c);
    }
    EEPROM.write(addr++, insideStatus[i]);
  }
  EEPROM.commit();
}

// =======================
// LOAD STUDENTS FROM EEPROM
// =======================
void loadFromEEPROM() {
  studentCount = EEPROM.read(0);
  if (studentCount > MAX_STUDENTS) studentCount = 0;
  int addr = 1;
  for (int i = 0; i < studentCount; i++) {
    char uidChars[UID_LENGTH + 1];
    char nameChars[NAME_LENGTH + 1];
    for (int j = 0; j < UID_LENGTH; j++) {
      uidChars[j] = EEPROM.read(addr++);
    }
    uidChars[UID_LENGTH] = '\0';
    for (int j = 0; j < NAME_LENGTH; j++) {
      nameChars[j] = EEPROM.read(addr++);
    }
    nameChars[NAME_LENGTH] = '\0';
    studentUID[i] = String(uidChars);
    studentName[i] = String(nameChars);
    insideStatus[i] = EEPROM.read(addr++);
  }
}

// Ensure live updates for all features
void handleData() {
  DynamicJsonDocument doc(512);

  doc["attendance"] = attendanceStatus;
  doc["mode"] = modeStatus;
  doc["rash"] = rashStatus;
  doc["accident"] = accidentStatus;
  doc["roll"] = rollAngle;
  doc["pitch"] = pitchAngle;
  doc["gyroZ"] = gyroZValue;

  JsonArray onboard = doc.createNestedArray("students_onboard");
  for (int i = 0; i < studentCount; i++) {
    if (insideStatus[i]) onboard.add(studentUID[i]);
  }

  String json;
  serializeJson(doc, json);

  // Print JSON to Serial Monitor
  Serial.println("--- JSON Sent ---");
  Serial.println(json);

  server.send(200, "application/json", json);
}

// Ensure register mode works correctly
void handleRegister() {
  if (server.hasArg("name")) {
    tempName = server.arg("name");
    registerMode = true;
    modeStatus = "Register Mode";
  }
  server.send(200, "text/plain", "OK");
}
