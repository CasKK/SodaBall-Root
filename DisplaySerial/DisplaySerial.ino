#include <MD_Parola.h>
#include <MD_MAX72xx.h>
#include <SPI.h>

#define HARDWARE_TYPE MD_MAX72XX::FC16_HW
#define MAX_DEVICES 1
#define CS_PIN 3

MD_Parola display = MD_Parola(HARDWARE_TYPE, CS_PIN, MAX_DEVICES);

// rounds is in tenths (e.g., 15 = 1.5)
int rounds = 0;
int lastRounds = 0;
bool animatingDisplay = false;
bool staticDisplay = false;

const int pinAdd1 = A0;
const int pinAdd05 = A1;
const int pinSub1 = A2;
const int pinSub05 = A3;
unsigned long lastMillis[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };
int debounceTime = 150;


//Serial comm stuff:
bool stringComplete = false;
String inputString = "";
uint16_t data[12];




void setup() {
  Serial.begin(9600);
  pinMode(pinAdd1, INPUT_PULLUP);
  pinMode(pinAdd05, INPUT_PULLUP);
  pinMode(pinSub1, INPUT_PULLUP);
  pinMode(pinSub05, INPUT_PULLUP);

  display.begin();
  display.setIntensity(5);
  display.displayClear();
  display.displayText("TEST", PA_CENTER, 50, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
  while (!display.displayAnimate()) {
  }
  display.displayReset();
}

void loop() {
  inputFromSerialStuff();

  if (!animatingDisplay || true) {
    // Handle buttons (active LOW)
    if (digitalRead(pinAdd1) == LOW) {
      if (lastMillis[0] + debounceTime < millis()) {
        rounds += 10;
        display.displayClear();
        display.displayReset();
        animatingDisplay = false;
      }
      lastMillis[0] = millis();
    } else if (digitalRead(pinAdd05) == LOW) {
      if (lastMillis[1] + debounceTime < millis()) {
        rounds += 5;
        display.displayClear();
        display.displayReset();
        animatingDisplay = false;
      }
      lastMillis[1] = millis();
    } else if (digitalRead(pinSub1) == LOW) {
      if (lastMillis[2] + debounceTime < millis()) {
        rounds -= 10;
        display.displayClear();
        display.displayReset();
        animatingDisplay = false;
      }
      lastMillis[2] = millis();
    } else if (digitalRead(pinSub05) == LOW) {
      if (lastMillis[3] + debounceTime < millis()) {
        rounds -= 5;
        display.displayClear();
        display.displayReset();
        animatingDisplay = false;
      }
      lastMillis[3] = millis();
    }
    if (digitalRead(data[0] == 1) {
      if (lastMillis[4] + debounceTime < millis()) {
        rounds += 10;
        display.displayClear();
        display.displayReset();
        animatingDisplay = false;
      }
      lastMillis[4] = millis();
    } else if (data[0] == 1) {
      if (lastMillis[5] + debounceTime < millis()) {
        rounds += 5;
        display.displayClear();
        display.displayReset();
        animatingDisplay = false;
      }
      lastMillis[5] = millis();
    } else if (data[0] == 1) {
      if (lastMillis[6] + debounceTime < millis()) {
        rounds -= 10;
        display.displayClear();
        display.displayReset();
        animatingDisplay = false;
      }
      lastMillis[6] = millis();
    } else if (data[0] == 1) {
      if (lastMillis[7] + debounceTime < millis()) {
        rounds -= 5;
        display.displayClear();
        display.displayReset();
        animatingDisplay = false;
      }
      lastMillis[7] = millis();
    }
  }
  
  if (rounds % 10 == 5) {
    if (animatingDisplay) {
      if (display.displayAnimate()) animatingDisplay = false;
    } else {
      display.displayClear();
      char msg[6];
      int whole = rounds / 10;
      snprintf(msg, sizeof(msg), "%d.5", whole);
      //Serial.println(msg);
      display.displayText(msg, PA_CENTER, 100, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
      animatingDisplay = true;
      staticDisplay = false;
    }
  } else if (rounds % 10 == 0 && !staticDisplay || rounds != lastRounds) {
    staticDisplay = true;
    animatingDisplay = false;
    lastRounds = rounds;
    display.displayClear();
    display.displayReset();
    //String msgga = String(rounds / 10);
    display.print(rounds / 10);
  }
  data[0] = 0;
}

void inputFromSerialStuff() {
  if (stringComplete) {
    stringComplete = false;
    int idx = 0;
    int start = 0;

    for (int i = 0; i <= inputString.length(); i++) {
      if (inputString[i] == ',' || inputString[i] == '\n' || i == inputString.length()) {
        String part = inputString.substring(start, i);
        part.trim();                          // remove spaces
        if (part.length() > 0 && idx < 12) {  // Only count if it's not empty
          data[idx] = part.toInt();
          idx++;
        }
        start = i + 1;
      }
    }
    if (idx == 12) {
      //Serial.println("Modtaget");
    } else {
      //Serial.println("ERROR: Expected 12 values, got " + String(idx));
    }
    inputString = "";
  }
}
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    if (inChar == '\n') {
      stringComplete = true;
    }
  }
}