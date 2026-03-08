// ==============================
// Smart Bus Tracker - ESP32
// ==============================

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <MPU6050.h>
#include <TinyGPS++.h>
#include <ArduinoJson.h>

// ==============================
// WIFI
// ==============================

const char* ssid = "Deshik";
const char* password = "129129129";

// ==============================
// SERVER
// ==============================

String serverURL = "http://172.24.180.1:5000/update"; 
// CHANGE THIS TO YOUR PC IP

// ==============================
// RFID
// ==============================

#define SS_PIN 15
#define RST_PIN 4

MFRC522 rfid(SS_PIN, RST_PIN);

// ==============================
// MPU6050
// ==============================

MPU6050 mpu;

// ==============================
// GPS
// ==============================

HardwareSerial SerialGPS(2);
TinyGPSPlus gps;

#define GPS_RX 16
#define GPS_TX 17

// ==============================
// STATUS VARIABLES
// ==============================

String accidentStatus = "Safe";
String rashStatus = "Driving Normal";

float rollAngle = 0;
float pitchAngle = 0;
float gyroZValue = 0;
float accMag = 0;

// ==============================
// GPS DATA
// ==============================

float latitude = 0;
float longitude = 0;
float speedKmph = 0;

// ==============================
// RFID
// ==============================

String lastUID = "";

// ==============================
// THRESHOLDS
// ==============================

float accidentThreshold = 2.5;
float tiltThreshold = 20.0;
float sharpTurnThreshold = 120.0;
float accidentGyroThreshold = 350.0;

// ==============================
// TIMERS
// ==============================

unsigned long lastPublish = 0;

// ==============================
// WIFI SETUP
// ==============================

void setupWiFi(){

  WiFi.begin(ssid,password);

  Serial.print("Connecting WiFi");

  while(WiFi.status()!=WL_CONNECTED){

    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected");
  Serial.println(WiFi.localIP());
}

// ==============================
// READ RFID
// ==============================

void readRFID(){

  if(!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial())
  return;

  String uid="";

  for(byte i=0;i<rfid.uid.size;i++){

    uid += String(rfid.uid.uidByte[i],HEX);
  }

  uid.toUpperCase();

  lastUID = uid;

  Serial.print("RFID UID: ");
  Serial.println(uid);

  rfid.PICC_HaltA();
}

// ==============================
// READ MPU6050
// ==============================

void readMPU(){

  int16_t ax,ay,az;
  int16_t gx,gy,gz;

  mpu.getMotion6(&ax,&ay,&az,&gx,&gy,&gz);

  float AccX = ax / 16384.0;
  float AccY = ay / 16384.0;
  float AccZ = az / 16384.0;

  gyroZValue = gz / 131.0;

  rollAngle = atan2(AccY,AccZ)*57.3;
  pitchAngle = atan2(-AccX,sqrt(AccY*AccY+AccZ*AccZ))*57.3;

  accMag = sqrt(AccX*AccX + AccY*AccY + AccZ*AccZ);

  // Rash Driving

  if(abs(rollAngle) > tiltThreshold ||
     abs(pitchAngle) > tiltThreshold ||
     abs(gyroZValue) > sharpTurnThreshold){

      rashStatus = "Rash Driving";
  }

  else{

      rashStatus = "Driving Normal";
  }

  // Accident

  if(accMag > accidentThreshold ||
     abs(gyroZValue) > accidentGyroThreshold){

      accidentStatus = "Accident Detected";
  }

  else{

      accidentStatus = "Safe";
  }
}

// ==============================
// READ GPS
// ==============================

void readGPS(){

  while(SerialGPS.available()){

    gps.encode(SerialGPS.read());
  }

  if(gps.location.isValid()){

    latitude = gps.location.lat();
    longitude = gps.location.lng();
  }

  if(gps.speed.isValid()){

    speedKmph = gps.speed.kmph();
  }
}

// ==============================
// SEND DATA TO FLASK
// ==============================

void publishStatus(){

  DynamicJsonDocument doc(512);

  doc["lat"] = latitude;
  doc["lng"] = longitude;
  doc["speed"] = speedKmph;

  doc["rash"] = rashStatus;
  doc["accident"] = accidentStatus;

  doc["roll"] = rollAngle;
  doc["pitch"] = pitchAngle;
  doc["gyro"] = gyroZValue;

  doc["accMag"] = accMag;

  doc["uid"] = lastUID;

  String payload;

  serializeJson(doc,payload);

  Serial.println("Sending Data:");
  Serial.println(payload);

  if(WiFi.status()==WL_CONNECTED){

    HTTPClient http;

    http.begin(serverURL);
    http.addHeader("Content-Type","application/json");

    int response = http.POST(payload);

    Serial.print("HTTP Response: ");
    Serial.println(response);

    http.end();
  }
}

// ==============================
// SETUP
// ==============================

void setup(){

  Serial.begin(115200);

  SPI.begin();
  rfid.PCD_Init();

  Wire.begin(21,22);
  mpu.initialize();

  SerialGPS.begin(9600,SERIAL_8N1,GPS_RX,GPS_TX);

  setupWiFi();
}

// ==============================
// LOOP
// ==============================

void loop(){

  readRFID();

  readMPU();

  readGPS();

  if(millis() - lastPublish > 2000){

    publishStatus();

    lastPublish = millis();
  }

}