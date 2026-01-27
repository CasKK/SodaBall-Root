#include <FastCRC.h>
#include <MD_Parola.h>   //Display libary
#include <MD_MAX72xx.h>  //Display libary
#include <SPI.h>         //Display libary
#define HARDWARE_TYPE MD_MAX72XX::FC16_HW  //For Display

FastCRC8 CRC8;

/* =========================
   CONFIGURATION
   ========================= */

const uint8_t ARDUINO_ID = 1;
int lastCommandSeq = -1;

const unsigned long retryInterval = 200;  // ms
const unsigned long debounceTime = 300;   // ms

const uint8_t lightSensorPin = A5;    //Light sensor lignal pin
const uint8_t coinBig = 8;            //For add big coin
const uint8_t coinSmall = 9;          //For add small coin
const uint8_t activateAirButton = 3;  //For start airRelay
const uint8_t airRelay = 4;           //7;                    //For airRelay
const uint8_t smokeRelay = 5;         //6;                  //For smokeRelay


const int MAX_DEVICES = 1;                 //For display
const int CS_PIN = 2;                      //For display
bool animatingDisplay = false;
bool staticDisplay = false;
MD_Parola display = MD_Parola(HARDWARE_TYPE, CS_PIN, MAX_DEVICES);  //Display

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

unsigned long lastMillis[4] = { 0, 0, 0, 0 };

/* =========================
   SEND/QUEUE FUNCTIONS
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

void sendCommandAck(int id, int seq) {
  char body[32];
  snprintf(body, sizeof(body), "A,%d,%d,OK", id, seq);

  uint8_t crc = CRC8.smbus((uint8_t*)body, strlen(body));

  Serial.print("$");
  Serial.print(body);
  Serial.print("*");
  Serial.print(crc, HEX);
  Serial.print("\n");
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
  if (id != ARDUINO_ID) return;

  if (type == 'A' && count > 0) {
    if (rxSeq == queue[head].seq) {
      // Pop queue
      head = (head + 1) % QUEUE_SIZE;
      count--;
      waitingForAck = false;
    }
  }
  if (type == 'R') {
    bool commandHandled = false;

    if (rxSeq <= lastCommandSeq) {
    // Already handled → ACK again, do nothing
    sendCommandAck(id, rxSeq);
    return;
    }
    lastCommandSeq = rxSeq;

    if (strcmp(msg, "air") == 0) {
      digitalWrite(airRelay, HIGH);
      commandHandled = true;
    } else if (strcmp(msg, "noair") == 0) {
      digitalWrite(airRelay, LOW);
      commandHandled = true;
    } else if (strcmp(msg, "smoke") == 0) {
      digitalWrite(smokeRelay, HIGH);
      commandHandled = true;
    } else if (strcmp(msg, "nosmoke") == 0) {
      digitalWrite(smokeRelay, LOW);
      commandHandled = true;
    }
    if (commandHandled) {
      sendCommandAck(id, rxSeq);
    }
  }
  if (type == 'D') {
    bool commandHandled = false;

    if (rxSeq <= lastCommandSeq) {
    // Already handled → ACK again, do nothing
    sendCommandAck(id, rxSeq);
    return;
    }
    lastCommandSeq = rxSeq;

    char *endptr;
    long number = strtol(msg, &endptr, 10);
    number = float(number) / 10;
    updateDisplay(number);

    if (commandHandled) {
      sendCommandAck(id, rxSeq);
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
  pinMode(coinBig, INPUT_PULLUP);
  pinMode(coinSmall, INPUT_PULLUP);
  pinMode(activateAirButton, INPUT_PULLUP);
  pinMode(airRelay, OUTPUT);
  pinMode(smokeRelay, OUTPUT);
  display.begin();
  display.setIntensity(5);
  display.displayClear();
  display.displayText("TEST", PA_CENTER, 50, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
  while (!display.displayAnimate()) {
  }
  display.displayReset();
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
  if (digitalRead(coinBig) == LOW) {
    if (debouncePassed(1)) {
      enqueueEvent('B', "coinBig");
    }
  }
  if (digitalRead(coinSmall) == LOW) {
    if (debouncePassed(2)) {
      enqueueEvent('B', "coinSmall");
    }
  }
  if (digitalRead(activateAirButton) == LOW) {
    if (debouncePassed(3)) {
      enqueueEvent('B', "Air");
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


void updateDisplay(float value) {
  static float lastDisplayedValue = -1.0;
  static bool lastWasStatic = false;

  bool isStaticDisplay = (value == floor(value) && value < 10.0);

  // Skip updating only if:
  // - value is static
  // - AND previously shown value was the same
  // - AND it was shown statically
  // - AND we are not animating
  if (isStaticDisplay && lastWasStatic && value == lastDisplayedValue && !animatingDisplay) {
    return;
  }

  // Handle scroll animation if in progress
  if (animatingDisplay) {
    if (display.displayAnimate()) {
      display.displayClear();
      display.displayReset();
      animatingDisplay = false;
      // Do NOT update lastDisplayedValue here — we want scrolling to repeat
    }
    return;
  }

  display.displayClear();

  if (isStaticDisplay) {
    display.displayReset();
    display.print((int)value);
    staticDisplay = true;
    animatingDisplay = false;
    lastDisplayedValue = value;
    lastWasStatic = true;
  } else {
    char msg[8];
    dtostrf(value, 4, 1, msg);  // Format to 1 decimal place
    display.displayText(msg, PA_CENTER, 100, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
    animatingDisplay = true;
    staticDisplay = false;
    lastWasStatic = false;  // Important! Tells next static value to show even if value is same
    // Don't update lastDisplayedValue — to keep scrolling
  }
}
