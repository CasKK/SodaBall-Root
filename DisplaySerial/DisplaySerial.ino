#include <MD_Parola.h>   //Display libary
#include <MD_MAX72xx.h>  //Display libary
#include <SPI.h>         //Display libary

//--------Pins and other constants----------
#define HARDWARE_TYPE MD_MAX72XX::FC16_HW  //For Display
const int MAX_DEVICES = 1;                 //For display
const int CS_PIN = 3;                      //For display
const int trigPin = 10;                    //For ultrasound sensor output
const int echoPin = 9;                     //For ultrasound sensor input
const int pinAdd1 = A0;                    //For add big coin
const int pinAdd05 = A1;                   //For add small coin
const int pinSub1 = A2;                    //For start airRelay
const int pinSub05 = A3;                   //For nothing currently
const int airRelay = 6;                    //For airRelay

//--------Objects----------
MD_Parola display = MD_Parola(HARDWARE_TYPE, CS_PIN, MAX_DEVICES);  //Display


//--------Variables----------
unsigned long lastMillis[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };  //Timetracking used for debounce
int debounceTime = 150;                                    //Unit: ms
bool animatingDisplay = false;
bool staticDisplay = false;
float rounds = 0;  //The displayed variable

//---------Ultrasound variables---------
unsigned long triggerTime = 0;
unsigned long echoStartTime = 0;
unsigned long echoEndTime = 0;
unsigned long duration = 0;
unsigned long lastMeasureTime = 0;
float distance = 0.0;
bool triggered = false;
bool waitingForEcho = false;

//-------Serial comm stuff--------
String inputString = "";                                            //Raw String input.
bool stringComplete = false;                                        //Used to only parse the String if it is complete.
uint16_t dataIn[12];                                                //Some values are reset to 0 after they are used.
uint16_t dataOut[12];                                               //All values are reset to 0 after they are sent.
uint16_t lastDataOut[12] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };  //Currently (31/05/25) used as a 0 to compare against.


void setup() {
  Serial.begin(9600);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(pinAdd1, INPUT_PULLUP);
  pinMode(pinAdd05, INPUT_PULLUP);
  pinMode(pinSub1, INPUT_PULLUP);
  pinMode(pinSub05, INPUT_PULLUP);
  pinMode(airRelay, OUTPUT);

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
    }
    lastMillis[0] = millis();
  } else if (digitalRead(pinAdd05) == LOW) {
    if (lastMillis[1] + debounceTime < millis()) {
      dataOut[1] = 1;
    }
    lastMillis[1] = millis();
  } else if (digitalRead(pinSub1) == LOW) {
    if (lastMillis[2] + debounceTime < millis()) {
      dataOut[2] = 1;
    }
    lastMillis[2] = millis();
  } /*else if (digitalRead(pinSub05) == LOW) {
    if (lastMillis[3] + debounceTime < millis()) {
      //dataOut[3] = 1;
    }
    lastMillis[3] = millis();
  }*/
  if (distance < 61 || distance > 70) {
    if (lastMillis[3] + 300 < millis()) {
      dataOut[3] = 1;
    }
    lastMillis[3] = millis();
  }
  /*if (dataIn[0] == 1) {
    rounds += 10;
    display.displayClear();
    display.displayReset();
    animatingDisplay = false;
  } else if (dataIn[2] == 1) {
    rounds += 5;
    display.displayClear();
    display.displayReset();
    animatingDisplay = false;
  } else if (dataIn[1] == 1) {
    rounds -= 10;
    display.displayClear();
    display.displayReset();
    animatingDisplay = false;
  } else if (dataIn[3] == 1) {
    rounds -= 5;
    display.displayClear();
    display.displayReset();
    animatingDisplay = false;
  }*/
  if (dataIn[5] == 1) {
    digitalWrite(airRelay, HIGH);
  } else {
    digitalWrite(airRelay, LOW);
  }

  //float displayValue = rounds / 10.0;
  updateDisplay(rounds);
  /*
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
    display.print(rounds / 10);
  }
  */
  //------------Ultrasound------------
  unsigned long currentTime = micros();

  // Every 50ms, start a new measurement
  if (!triggered && currentTime - lastMeasureTime >= 30000) {
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);  // minimal blocking (2 us)
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);  // 10 us trigger pulse
    digitalWrite(trigPin, LOW);
    triggerTime = micros();
    triggered = true;
    waitingForEcho = true;
  }

  // Wait for echo to go HIGH
  if (triggered && waitingForEcho && digitalRead(echoPin) == HIGH) {
    echoStartTime = micros();
    waitingForEcho = false;
  }

  // Wait for echo to go LOW
  if (triggered && !waitingForEcho && digitalRead(echoPin) == LOW) {
    echoEndTime = micros();
    duration = echoEndTime - echoStartTime;
    distance = duration * 0.0343 / 2.0;  // Convert to cm
    triggered = false;
    lastMeasureTime = currentTime;

    
    Serial.print("Distance: ");
    Serial.print(distance);
    Serial.println(" cm");
    
  }



  sendData();
  dataIn[0] = 0;
  dataIn[1] = 0;
  dataIn[2] = 0;
  dataIn[3] = 0;
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
    if (idx == 12) {
      //Serial.println("Modtaget");
    } else {
      //Serial.println("ERROR: Expected 12 values, got " + String(idx));
    }
    inputString = "";
    rounds = float(dataIn[4]) / 10;
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
  if (memcmp(dataOut, lastDataOut, sizeof(dataOut)) != 0) {
    String send_this = "";
    for (int i = 0; i < 12; i++) {
      send_this += String(dataOut[i]);
      if (i < 11) send_this += ",";
    }
    Serial.println(send_this);
    for (int i = 0; i < 12; i++) {
      dataOut[i] = 0;
      //lastDataOut[i] = 0;
    }
    //Serial.println("0,0,0,0,0,0,0,0,0,0,0,0");
  }
}
void updateDisplay(float value) {
  static float lastDisplayedValue = -1.0;
  // If it's the same value and not animating, skip updating
  if (value == lastDisplayedValue && !animatingDisplay) return;
  // Continue animation until complete
  if (animatingDisplay) {
    if (display.displayAnimate()) {
      display.displayClear();
      display.displayReset();
      //animatingDisplay = false;
      //lastDisplayedValue = value;
    }
    return;
  }
  display.displayClear();
  // Static only for whole numbers < 10
  if (value == floor(value) && value < 10.0) {
    display.displayReset();
    display.print((int)value);
    staticDisplay = true;
    animatingDisplay = false;
    lastDisplayedValue = value;
  } else {
    char msg[8];
    dtostrf(value, 4, 1, msg);  // 1 decimal place, space padded
    display.displayText(msg, PA_CENTER, 100, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
    animatingDisplay = true;
    staticDisplay = false;
  }
}