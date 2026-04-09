#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>

const char* ssid     = "SodaBall";
const char* password = "12321232";
const char* host     = "10.42.0.255";  // your PC's local IP
const int   port     = 5005;

WiFiUDP udp;

void sendCommand(const char* cmd) {
  udp.beginPacket(host, port);
  udp.write((const uint8_t*)cmd, strlen(cmd));
  udp.endPacket();
}

void setup() {
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  udp.begin(5005);  // local port, can be anything
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    delay(500);
    return;
  }
  
  sendCommand("goal 1");
  sendCommand("air 2");
  delay(2000);
}


// then on button press:
// etc.