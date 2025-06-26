#include <MD_Parola.h>   //Display libary
#include <MD_MAX72xx.h>  //Display libary
#include <SPI.h>         //Display libary

//--------Pins and other constants----------
#define HARDWARE_TYPE MD_MAX72XX::FC16_HW  //For Display
const int MAX_DEVICES = 1;                 //For display
const int CS_PIN = 2;                      //For display
const int lightSensorPin = A5;             //Light sensor lignal pin
const int pinAdd1 = 8;                     //For add big coin
const int pinAdd05 = 9;                    //For add small coin
const int activateAirButton = 3;           //For start airRelay
const int pinSub05 = A3;                   //For nothing currently
const int airRelay = 4;                    //7;                    //For airRelay
const int smokeRelay = 5;                  //6;                  //For airRelay

//--------Objects----------
MD_Parola display = MD_Parola(HARDWARE_TYPE, CS_PIN, MAX_DEVICES);  //Display


//--------Variables----------
unsigned long lastMillis[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };  //Timetracking used for debounce
int debounceTime = 250;                                    //Unit: ms
bool animatingDisplay = false;
bool staticDisplay = false;
float rounds = 0;              //The displayed variable
int connectionGoodTime = 200;  //Time between connection checks

//Beam break
int lightValue = 0.0;


//-------Serial comm stuff--------
String inputString = "";                                            //Raw String input.
bool stringComplete = false;                                        //Used to only parse the String if it is complete.
uint16_t dataIn[12];                                                //Some values are reset to 0 after they are used.
uint16_t dataOut[12];                                               //All values are reset to 0 after they are sent.
uint16_t lastDataOut[12] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };  //Currently (31/05/25) used as a 0 to compare against.


void setup() {
  Serial.begin(9600);

  pinMode(pinAdd1, INPUT_PULLUP);
  pinMode(pinAdd05, INPUT_PULLUP);
  pinMode(activateAirButton, INPUT_PULLUP);
  pinMode(pinSub05, INPUT_PULLUP);
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

void loop() {
  parseInputFromSerial();

  if (digitalRead(pinAdd1) == LOW) {
    if (lastMillis[0] + debounceTime < millis()) {
      dataOut[0] = 1;
      //Serial.println("20");
    }
    lastMillis[0] = millis();
  } else {
    dataOut[0] = 0;
  }
  if (digitalRead(pinAdd05) == LOW) {
    if (lastMillis[1] + debounceTime < millis()) {
      dataOut[1] = 1;
      //Serial.println("10");
    }
    lastMillis[1] = millis();
  } else {
    dataOut[1] = 0;
  }

  if (digitalRead(activateAirButton) == LOW) {
    if (lastMillis[2] + debounceTime < millis()) {
      dataOut[2] = 1;
    }
    lastMillis[2] = millis();
  } else {
    dataOut[2] = 0;
  } /*else if (digitalRead(pinSub05) == LOW) {
    if (lastMillis[3] + debounceTime < millis()) {
      //dataOut[3] = 1;
    }
    lastMillis[3] = millis();
  }*/

  /*
  if (millis() >= lastMillis[7] + connectionGoodTime) {
    lastMillis[7] = millis();
    dataOut[4] = connectionGoodTime;
  }
*/

  lightValue = analogRead(lightSensorPin);
  if (lightValue > 200) {
    if (lastMillis[3] + 300 < millis()) {
      dataOut[3] = 1;
    }
    lastMillis[3] = millis();
  } else {
    dataOut[3] = 0;
  }


  if (dataIn[5] == 1) {
    digitalWrite(airRelay, HIGH);
    //Serial.println("air");
    dataOut[5] = 1;
  } else {
    digitalWrite(airRelay, LOW);
    dataOut[5] = 0;
  }

  if (dataIn[6] == 1) {
    digitalWrite(smokeRelay, HIGH);
    dataOut[6] = 1;
  } else {
    digitalWrite(smokeRelay, LOW);
    dataOut[6] = 0;
  }

  updateDisplay(rounds);

  sendData();
}

void parseInputFromSerial() {
  if (stringComplete) {
    stringComplete = false;
    int idx = 0;
    int start = 0;

    for (int i = 0; i <= inputString.length(); i++) {
      if (inputString[i] == ',' || inputString[i] == '\n' || i == inputString.length()) {
        String part = inputString.substring(start, i);
        part.trim();                          // remove spaces
        if (part.length() > 0 && idx < 12) {  // Only count if it's not empty
          dataIn[idx] = part.toInt();
          idx++;
        }
        start = i + 1;
      }
    }
    //if (idx == 12) {
    //Serial.println("Modtaget");
    //} else {
    //Serial.println("ERROR: Expected 12 values, got " + String(idx));
    //}
    inputString = "";
    rounds = float(dataIn[0]) / 10;
    animatingDisplay = false;
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

void sendData() {
  if (memcmp(dataOut, lastDataOut, sizeof(dataOut)) != 0 || millis() >= lastMillis[7] + connectionGoodTime) {
    dataOut[4] = connectionGoodTime;
    lastMillis[7] = millis();
    String send_this = "";
    for (int i = 0; i < 12; i++) {
      send_this += String(dataOut[i]);
      if (i < 11) send_this += ",";
    }
    Serial.println(send_this);
    for (int i = 0; i < 10; i++) {
      //dataOut[i] = 0;
      lastDataOut[i] = dataOut[i];
    }
    //Serial.println("0,0,0,0,0,0,0,0,0,0,0,0");
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
