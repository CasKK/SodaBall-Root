
const int airRelay = 4;                    //For airRelay
const int smokeRelay = 5;                  //For airRelay

//-------Serial comm stuff--------
String inputString = "";                                            //Raw String input.
bool stringComplete = false;                                        //Used to only parse the String if it is complete.
uint16_t dataIn[12];                                                //Some values are reset to 0 after they are used.


void setup() {
  Serial.begin(9600);

  pinMode(airRelay, OUTPUT);
  pinMode(smokeRelay, OUTPUT);

}

void loop() {
  parseInputFromSerial();

  if (dataIn[5] == 1) {
    digitalWrite(airRelay, HIGH);
    //Serial.println("air");
  } else {
    digitalWrite(airRelay, LOW);
  }

  if (dataIn[6] == 1) {
    digitalWrite(smokeRelay, HIGH);
  } else {
    digitalWrite(smokeRelay, LOW);
  }

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

