import controlP5.*;
import processing.serial.*;
import processing.sound.*;

SoundFile file;
float volume = 0;
boolean fadingIn = true;
boolean playSoundVariable = false;
int swVar = 0;
int bigCoinAirValue = 10;
int smallCoinAirValue = 5;
boolean airOn = false;
double airStartMillis;
double oneAirTime = 10000;

ControlP5 cp5;
Team teamA, teamB;
Button sub05Button1, sub05Button, add05Button, sub1Button, add1Button;

void setup() {
  size(1625, 900);

  cp5 = new ControlP5(this);

  teamA = new Team(this, cp5, 1);
  teamB = new Team(this, cp5, 2);

  editUI(600, 10);
}


void draw() {

  background(200);



  teamA.readData();

  teamB.readData();

  //if (teamA.lastDataIn[0] != teamA.dataIn[0] || teamA.lastDataIn[1] != teamA.dataIn[1] || teamA.lastDataIn[2] != teamA.dataIn[2] || teamA.lastDataIn[3] != teamA.dataIn[3]) {
  //  if (teamA.dataIn[0] == 1) {
  //    add1ButtonFunction();
  //    //teamA.dataIn[0] = 0;
  //  }
  //  for (int i = 0; i < 12; i++) {
  //    teamA.dataIn[i] = 0;
  //  }
  //}
  teamA.updateValues();


  if (airOn) airOnFunction();
}



void editUI(int x, int y) {
  add1Button = cp5.addButton("add1ButtonFunction")
    .setLabel("+1")
    .setSize(60, 30)
    .setPosition(x, y);
  sub1Button = cp5.addButton("sub1ButtonFunction")
    .setLabel("-1")
    .setSize(60, 30)
    .setPosition(x + 70, y);
  add05Button = cp5.addButton("add05ButtonFunction")
    .setLabel("+.5")
    .setSize(60, 30)
    .setPosition(x, y + 40);
  sub05Button = cp5.addButton("sub05ButtonFunction")
    .setLabel("-.5")
    .setSize(60, 30)
    .setPosition(x + 70, y + 40);
  sub05Button1 = cp5.addButton("sub05ButtonFunction1")
    .setLabel("-.5")
    .setSize(60, 30)
    .setPosition(x + 170, y + 140);
}

void add1ButtonFunction() {
  //teamA.dataOut[0] = 1;
  //teamA.sendData();
  //teamA.dataOut[0] = 0;
}

void sub1ButtonFunction() {
  //teamA.dataOut[1] = 1;
  //teamA.sendData();
  //teamA.dataOut[1] = 0;
}

void add05ButtonFunction() {
  //teamA.dataOut[2] = 1;
  //teamA.sendData();
  //teamA.dataOut[2] = 0;
}

void sub05ButtonFunction() {
  //teamA.dataOut[3] = 1;
  //teamA.sendData();
  //teamA.dataOut[3] = 0;
  switch(swVar) {
  case 0:
    teamA.dataOut[4] = 10;
    teamA.sendData();
    swVar += 1;
    break;
  case 1:
    teamA.dataOut[4] = 15;
    teamA.sendData();
    swVar += 1;
    break;
  case 2:
    teamA.dataOut[4] = 30;
    teamA.sendData();
    swVar += 1;
    break;
  case 3:
    teamA.dataOut[4] = 23;
    teamA.sendData();
    swVar += 1;
    break;
  case 4:
    teamA.dataOut[4] = 73;
    teamA.sendData();
    swVar = 0;
    break;
  }
}

void airOnFunction() {
  if (!airOn) {
    airStartMillis = millis();
    airOn = true;
  } else if (airStartMillis + oneAirTime <= millis()) {
    airOn = false;
    teamA.dataOut[5] = 0;
    teamB.dataOut[5] = 0;
    teamA.sendData();
    teamB.sendData();
  }
}

void soundShitter() {
  playSoundVariable = !playSoundVariable;
  if (playSoundVariable) {
    volume = 1;
    file = new SoundFile(this, "lyd1.mp3");
    file.amp(volume);
    file.play();
  } else {
    file.stop();
  }
}

void fadeSound() {
  volume -= 0.01;
  file.amp(volume);
  if (volume <= 0) {
    playSoundVariable = false;
    file.stop();
  }
}


void keyPressed() {         //keyPressed is a built-in function that is called once every time a key is pressed.
  if (keyCode==65) {        //To check what key is pressed, simple "if".
    //keyVariableA = true;    //This variable is (at the time of writing this) being used for drawing something. It is therefore made like a flip-flop, to draw it every frame and not just once.
  }
  if (keyCode==66) {
    saveStrings("dataOut1", teamA.messageArrayOut);
    saveStrings("dataIn1", teamA.messageArrayIn);
    saveStrings("dataOut2", teamB.messageArrayOut);
    saveStrings("dataIn2", teamB.messageArrayIn);
  }
}
