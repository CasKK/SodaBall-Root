#include <FastCRC.h>

FastCRC8 CRC8;

const uint8_t ARDUINO_ID = 1;
uint8_t seq = 0;

unsigned long lastSend = 0;
bool waitingForAck = false;


const int lightSensorPin = A5;  //Light sensor lignal pin
int lightValue = 0.0;           //Beam break

unsigned long lastMillis[3] = { 0, 0, 0 };  //Timetracking used for debounce
int debounceTime = 250;                     //Unit: ms


void sendEvent(const char* type, const char* payload) {
  char body[64];
  snprintf(body, sizeof(body),
           "%s,%d,%d,%s", type, ARDUINO_ID, seq, payload);

  uint8_t crc = CRC8.smbus((uint8_t*)body, strlen(body));

  Serial.print("$");
  Serial.print(body);
  Serial.print("*");
  Serial.print(crc, HEX);
  Serial.print("\n");

  waitingForAck = true;
  lastSend = millis();
}

void resend() {

  sendEvent("G", "LEFT");


}


void setup() {
  Serial.begin(115200);
}

void loop() {
  // Example trigger (replace with sensor)
  lightValue = analogRead(lightSensorPin);
  if (!waitingForAck && lightValue > 200) {
    if (lastMillis[0] + debounceTime < millis()) {
    sendEvent("G", "LEFT");
    }
    lastMillis[0] = millis();
  }

  if (!waitingForAck && digitalRead(pinAdd1) == LOW) {
    if (lastMillis[1] + debounceTime < millis()) {
    sendEvent("B", "Start");
    }
    lastMillis[1] = millis();
  }

  // Retry if ACK missing
  if (waitingForAck && millis() - lastSend > 200) {
    resend();
  }

  // Read incoming ACK
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    handleLine(line);
  }
}

void handleLine(String line) {
  if (!line.startsWith("$") || line.indexOf('*') == -1) return;

  int star = line.indexOf('*');
  String body = line.substring(1, star);
  uint8_t recvCrc = strtoul(line.substring(star + 1).c_str(), NULL, 16);

  uint8_t calcCrc = CRC8.smbus((uint8_t*)body.c_str(), body.length());
  if (recvCrc != calcCrc) return;

  // Parse
  char type;
  int id, rxSeq;
  char msg[8];

  sscanf(body.c_str(), "%c,%d,%d,%7s", &type, &id, &rxSeq, msg);

  if (type == 'A' && rxSeq == seq) {
    waitingForAck = false;
    seq++;  // advance only after confirmed delivery
  }
}
