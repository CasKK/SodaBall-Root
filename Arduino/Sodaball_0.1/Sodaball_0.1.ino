#include <FastCRC.h>

FastCRC8 CRC8;

/* =========================
   CONFIGURATION
   ========================= */

const uint8_t ARDUINO_ID = 1;

const unsigned long retryInterval = 200;   // ms
const unsigned long debounceTime  = 300;   // ms

const uint8_t lightSensorPin = A0;
const uint8_t buttonPin     = 2;

/* =========================
   MESSAGE QUEUE
   ========================= */

#define QUEUE_SIZE 8
#define PAYLOAD_SIZE 32

struct OutgoingMessage {
  char type;
  char payload[PAYLOAD_SIZE];
  uint8_t seq;
};

OutgoingMessage queue[QUEUE_SIZE];
uint8_t head = 0;
uint8_t tail = 0;
uint8_t count = 0;

uint8_t nextSeq = 0;

/* =========================
   STATE
   ========================= */

bool waitingForAck = false;
unsigned long lastSend = 0;

unsigned long lastMillis[2] = {0, 0};

/* =========================
   QUEUE FUNCTIONS
   ========================= */

bool enqueueEvent(char type, const char* payload) {
  if (count >= QUEUE_SIZE) {
    // Queue full → drop event or handle error
    return false;
  }

  queue[tail].type = type;
  strncpy(queue[tail].payload, payload, PAYLOAD_SIZE - 1);
  queue[tail].payload[PAYLOAD_SIZE - 1] = '\0';
  queue[tail].seq = nextSeq++;

  tail = (tail + 1) % QUEUE_SIZE;
  count++;
  return true;
}

void sendHead() {
  if (count == 0) return;

  OutgoingMessage& msg = queue[head];

  char body[64];
  snprintf(body, sizeof(body),
           "%c,%d,%d,%s",
           msg.type,
           ARDUINO_ID,
           msg.seq,
           msg.payload);

  uint8_t crc = CRC8.smbus((uint8_t*)body, strlen(body));

  Serial.print("$");
  Serial.print(body);
  Serial.print("*");
  Serial.print(crc, HEX);
  Serial.print("\n");

  lastSend = millis();
  waitingForAck = true;
}

/* =========================
   SERIAL RECEIVE
   ========================= */

void handleLine(String line) {
  if (!line.startsWith("$") || line.indexOf('*') == -1) return;

  int star = line.indexOf('*');
  String body = line.substring(1, star);
  uint8_t recvCrc = strtoul(line.substring(star + 1).c_str(), NULL, 16);

  uint8_t calcCrc = CRC8.smbus((uint8_t*)body.c_str(), body.length());
  if (recvCrc != calcCrc) return;

  char type;
  int id;
  int rxSeq;
  char msg[8];

  int parsed = sscanf(body.c_str(), "%c,%d,%d,%7s",
                      &type, &id, &rxSeq, msg);
  if (parsed < 3) return;

  if (type == 'A' && count > 0) {
    if (rxSeq == queue[head].seq) {
      // Pop queue
      head = (head + 1) % QUEUE_SIZE;
      count--;
      waitingForAck = false;
    }
  }
}

/* =========================
   DEBOUNCE HELPERS
   ========================= */

bool debouncePassed(uint8_t index) {
  unsigned long now = millis();
  if (now - lastMillis[index] >= debounceTime) {
    lastMillis[index] = now;
    return true;
  }
  lastMillis[index] = now;
  return false;
}

/* =========================
   SETUP
   ========================= */

void setup() {
  Serial.begin(115200);

  pinMode(buttonPin, INPUT_PULLUP);
}

/* =========================
   LOOP
   ========================= */

void loop() {

  /* ---- Goal sensor ---- */
  int lightValue = analogRead(lightSensorPin);
  if (lightValue > 200) {
    if (debouncePassed(0)) {
      enqueueEvent('G', "LEFT");
    }
  }

  /* ---- Button ---- */
  if (digitalRead(buttonPin) == LOW) {
    if (debouncePassed(1)) {
      enqueueEvent('B', "START");
    }
  }

  /* ---- Send next message ---- */
  if (!waitingForAck && count > 0) {
    sendHead();
  }

  /* ---- Retry ---- */
  if (waitingForAck && millis() - lastSend > retryInterval) {
    sendHead();  // resend same head
  }

  /* ---- Receive ---- */
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    handleLine(line);
  }
}
