#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>

const char* ssid     = "SodaBall";
const char* password = "12321232";
const char* host     = "10.42.0.255";
const int   port     = 5005;

WiFiUDP udp;

unsigned long lastMillis[10] = { 0 };
const unsigned long debounceTime = 200;

const uint8_t air        = 12;
const uint8_t noair      = 13;
const uint8_t coinUp     = 14;
const uint8_t coinDown   = 15;
const uint8_t goal       = 16;
const uint8_t scoreUp    = 17;
const uint8_t scoreDown  = 18;
const uint8_t profileUp  = 19;
const uint8_t profileDown = 23;
const uint8_t reset      = 27;
const uint8_t side       = 32;

int side1 = 0;

void sendCommand(const char* cmd) {
  udp.beginPacket(host, port);
  udp.write((const uint8_t*)cmd, strlen(cmd));
  udp.endPacket();
}

bool debouncePassed(uint8_t index) {
  unsigned long now = millis();
  if (now - lastMillis[index] >= debounceTime) {
    lastMillis[index] = now;
    return true;
  }
  return false;
}

void setup() {
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  udp.begin(5005);
  pinMode(air,         INPUT_PULLUP);
  pinMode(noair,       INPUT_PULLUP);
  pinMode(coinUp,      INPUT_PULLUP);
  pinMode(coinDown,    INPUT_PULLUP);
  pinMode(goal,        INPUT_PULLUP);
  pinMode(scoreUp,     INPUT_PULLUP);
  pinMode(scoreDown,   INPUT_PULLUP);
  pinMode(profileUp,   INPUT_PULLUP);
  pinMode(profileDown, INPUT_PULLUP);
  pinMode(reset,       INPUT_PULLUP);
  pinMode(side,        INPUT_PULLUP);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    delay(500);
    return;
  }

  side1 = (digitalRead(side) == LOW) ? 1 : 0;

  // air <team>
  if (digitalRead(air) == LOW) {
    if (debouncePassed(0)) {
      String msg = "air " + String(side1);
      sendCommand(msg.c_str());
    }
  }

  // noair
  if (digitalRead(noair) == LOW) {
    if (debouncePassed(1)) {
      sendCommand("noair");
    }
  }

  // money <team> +10
  if (digitalRead(coinUp) == LOW) {
    if (debouncePassed(2)) {
      String msg = "money " + String(side1) + " 10";
      sendCommand(msg.c_str());
    }
  }

  // money <team> -10
  if (digitalRead(coinDown) == LOW) {
    if (debouncePassed(3)) {
      String msg = "money " + String(side1) + " -10";
      sendCommand(msg.c_str());
    }
  }

  // goal <team>
  if (digitalRead(goal) == LOW) {
    if (debouncePassed(4)) {
      String msg = "goal " + String(side1);
      sendCommand(msg.c_str());
    }
  }

  // score <team> +1
  if (digitalRead(scoreUp) == LOW) {
    if (debouncePassed(5)) {
      String msg = "score " + String(side1) + " 1";
      sendCommand(msg.c_str());
    }
  }

  // score <team> -1
  if (digitalRead(scoreDown) == LOW) {
    if (debouncePassed(6)) {
      String msg = "score " + String(side1) + " -1";
      sendCommand(msg.c_str());
    }
  }

  // profile <node> +1
  if (digitalRead(profileUp) == LOW) {
    if (debouncePassed(7)) {
      String msg = "profile " + String(side1) + " 1";
      sendCommand(msg.c_str());
    }
  }

  // profile <node> -1
  if (digitalRead(profileDown) == LOW) {
    if (debouncePassed(8)) {
      String msg = "profile " + String(side1) + " -1";
      sendCommand(msg.c_str());
    }
  }

  // reset
  if (digitalRead(reset) == LOW) {
    if (debouncePassed(9)) {
      sendCommand("reset");
    }
  }
}