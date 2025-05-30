import controlP5.*;
import processing.serial.*;
import processing.sound.*;

SoundFile file;
float volume = 0;
boolean fadingIn = true;
boolean playSoundVariable = false;

ControlP5 cp5;
Team teamA, teamB;
Button sub05Button1, sub05Button, add05Button, sub1Button, add1Button;

void setup() {
  size(1625, 900);

  cp5 = new ControlP5(this);

  teamA = new Team(this, cp5, 1);
  teamB = new Team(this, cp5, 2);

  //connectionUI(10, 10);
  editUI(600, 10);
}


void draw() {

  background(200);



  teamA.readData();

  teamB.readData();

  if (teamA.lastDataIn[0] != teamA.dataIn[0] || teamA.lastDataIn[1] != teamA.dataIn[1] || teamA.lastDataIn[2] != teamA.dataIn[2] || teamA.lastDataIn[3] != teamA.dataIn[3]) {
    add1ButtonFunction();
    if (teamA.dataIn[0] == 1) {
      add1ButtonFunction();
      //teamA.dataIn[0] = 0;
    }
    for (int i = 0; i < 12; i++) {
      teamA.lastDataIn[i] = teamA.dataIn[i];
    }
  }
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
  teamA.dataOut[0] = 1;
  teamA.sendData();
  teamA.dataOut[0] = 0;
}

void sub1ButtonFunction() {
  teamA.dataOut[1] = 1;
  teamA.sendData();
  teamA.dataOut[1] = 0;
}

void add05ButtonFunction() {
  teamA.dataOut[2] = 1;
  teamA.sendData();
  teamA.dataOut[2] = 0;
}

void sub05ButtonFunction() {
  teamA.dataOut[3] = 1;
  teamA.sendData();
  teamA.dataOut[3] = 0;
}


void sub05ButtonFunction1() {
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
