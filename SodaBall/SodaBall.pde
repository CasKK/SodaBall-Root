import controlP5.*;
import processing.serial.*;
import processing.sound.*;

import java.awt.Toolkit;


SoundFile file, soundTeamA, soundTeamB;
float volume = 0;
boolean fadingIn = true;
boolean playSoundVariable = false;
int swVar = 0;
int bigCoinAirValue = 20;
int smallCoinAirValue = 10;
int airThesholdValue = 10;
boolean airOn = false;
boolean smokeOn = false;
boolean hasSentSmokeSignal = false;
int smokeTeamId = 0;
double airStartMillis;
double smokeStartMillis;
double oneAirTime = 5000; //ms
double smokeStopEarlyTime = 1000;
double smokeStartLateTime = 1000;

ControlP5 cp5;
Team teamA, teamB;

void setup() {
  size(1625, 900);

  cp5 = new ControlP5(this);
  soundTeamA = new SoundFile(this, "goalSoundTeamA.mp3");
  soundTeamB = new SoundFile(this, "goalSoundTeamB.mp3");
  soundTeamA.amp(1);
  soundTeamB.amp(1);
  teamA = new Team(this, cp5, soundTeamA, 0);
  teamB = new Team(this, cp5, soundTeamB, 1);




  //editUI(600, 10);
}


void draw() {

  background(200);



  teamA.readData();

  teamB.readData();

  if (airOn) airOnFunction();
  if (smokeOn) smokeOnFunction(smokeTeamId);
  if (teamA.goalMode) teamA.goalFunction();
  if (teamB.goalMode) teamB.goalFunction();

  if (teamA.connection1Time + teamA.lastConnection1Time > millis()) {
    fill(0, 255, 0);
    rect(40, 100, 10, 10);
  }
  if (teamB.connection1Time + teamB.lastConnection1Time > millis()) {
    fill(0, 255, 0);
    rect(40 + 800, 100, 10, 10);
  }
  if (teamA.connection2Time + teamA.lastConnection2Time > millis()) {
    fill(0, 255, 0);
    rect(40, 100 + 450, 10, 10);
  }
  if (teamB.connection2Time + teamB.lastConnection2Time > millis()) {
    fill(0, 255, 0);
    rect(40 + 800, 100 + 450, 10, 10);
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
void smokeOnFunction (int id) {
  if (!smokeOn) {
    smokeStartMillis = millis();
    smokeOn = true;
  } else if (airStartMillis + smokeStartLateTime <= millis() && airStartMillis + oneAirTime - smokeStopEarlyTime > millis()) {
    if (!hasSentSmokeSignal) {
      hasSentSmokeSignal = true;
      if (id == 0)teamA.dataOut[6] = 1;
      if (id == 1)teamB.dataOut[6] = 1;
      teamA.sendData();
      teamB.sendData();
    }
  } else if (airStartMillis + oneAirTime - smokeStopEarlyTime <= millis()) {
    smokeOn = false;
    hasSentSmokeSignal = false;
    teamA.dataOut[6] = 0;
    teamB.dataOut[6] = 0;
    teamA.sendData();
    teamB.sendData();
  }
}


void keyPressed() {         //keyPressed is a built-in function that is called once every time a key is pressed.
  if (keyCode==65) {        //To check what key is pressed.
    //keyVariableA = !keyVariableA;    //This variable is (at the time of writing this) being used for drawing something. It is therefore made like a flip-flop, to draw it every frame and not just once.
  }
  if (keyCode==66) {
    saveStrings("dataOut1", teamA.connection1.messageArrayOut);
    saveStrings("dataIn1", teamA.connection1.messageArrayIn);
    saveStrings("dataOut2", teamA.connection2.messageArrayOut);
    saveStrings("dataIn2", teamA.connection2.messageArrayIn);
  }
}
