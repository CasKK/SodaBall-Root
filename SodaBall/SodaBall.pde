import controlP5.*;
import processing.serial.*;

import processing.sound.*;

SoundFile file;
float volume = 0;
boolean fadingIn = true;
boolean playSoundVariable = false;

ControlP5 cp5;
Serial serial, serial1;
Textarea receivedArea, receivedArea1;
Println arduinoConsole, arduinoConsole1;
Button sub05Button1, connectionButton, connectionButton1, toggleConnectionUIButton;
ScrollableList portlist, portlist1;
ScrollableList baudlist, baudlist1;
boolean connectButtonStatus = false; //Status of the connect button
boolean connectButtonStatus1 = false;
boolean toggleUIBool = false;
String selectedport, selectedport1;
int selectedbaudrate, selectedbaudrate1;

//float[] lastSentValue = new float[15]; //Track what values was last sent to the arduino.

//Edit UI
Button sub05Button, add05Button, sub1Button, add1Button;
int[] dataOut = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
String[] messageArrayOut = {"a", "b"};
String[] messageArrayIn = {"c", "d"};

void setup() {
  size(1625, 900);


  cp5 = new ControlP5(this);
  connectionUI(10, 10);
  editUI(600, 10);
}


void draw() {

  background(200);



  readData();

  if (playSoundVariable) fadeSound();
}














void toggleConnectionUI() { //Will toggle the UI. Runs when "toggleUI" button is pressed.

  toggleUIBool = !toggleUIBool;
  connectionButton.setVisible(toggleUIBool);
  portlist.setVisible(toggleUIBool);
  baudlist.setVisible(toggleUIBool);
  receivedArea.setVisible(toggleUIBool);
  connectionButton1.setVisible(toggleUIBool);
  portlist1.setVisible(toggleUIBool);
  baudlist1.setVisible(toggleUIBool);
  receivedArea1.setVisible(toggleUIBool);
}



public void sendData() {
  try {
    String message = "" ;

    for (int i = 0; i < 12; i++) {
      String messageValue = Integer.toString(dataOut[i]);
      message = message+messageValue;
      if (i<11) message = message + ",";
    }

    serial.write(message);
    serial.write(10);
    serial1.write(message);
    serial1.write(10);
    messageArrayOut = append(messageArrayOut, message);

    //      for (int i = 0; i < 12; i++) {
    //        if (i < 6) {
    //          lastSentValue[i] = (float)targetAngle[i];
    //        } else {
    //          lastSentValue[i] = (float)speed[i-6];
    //        }
    //      }
    //      lastSentValue[12] = gripperVariable;
    //      lastSentValue[13] = vialBoxVariable;
    //      lastSentValue[14] = inversionVariable;


    String data = "";
    while (serial.available() > 0) {
      data = serial.readStringUntil(10);
      if (data != null) {
        receivedArea.setText("Arduino: " + data);
        messageArrayIn = append(messageArrayIn, data);
        //utils.drawResult(data, 10, 600);
      }
    }
    String data1 = "";
    while (serial1.available() > 0) {
      data1 = serial1.readStringUntil(10);
      if (data1 != null) {
        receivedArea1.setText("Arduino1: " + data1);
        messageArrayIn = append(messageArrayIn, data1);
        //utils.drawResult(data1, 10, 700);
      }
    }
  }
  catch (Exception e) {
    //messageArrayIn = append(messageArrayIn, e.getMessage());

    println("Serial port error: " + e.getMessage());
  }
}

int[] dataIn;
int[] dataIn1;

public void readData() {
  String data = "";
  String data1 = "";
  try {

    while (serial.available() > 0) {
      data = serial.readStringUntil(10);
      if (data != null) {
        receivedArea.setText("Arduino: " + data);
        messageArrayIn = append(messageArrayIn, data);
        //utils.drawResult(data, 10, 600);
      }
    }

    while (serial1.available() > 0) {
      data1 = serial1.readStringUntil(10);
      if (data1 != null) {
        receivedArea1.setText("Arduino1: " + data1);
        messageArrayIn = append(messageArrayIn, data1);
        //utils.drawResult(data1, 10, 700);
      }
    }
  }
  catch (Exception e) {
    //messageArrayIn = append(messageArrayIn, e.getMessage());

    println("Serial port error: " + e.getMessage());
  }

  String[] dataInTemp1 = split(data1, ",");
  dataIn1 = new int[dataInTemp1.length];
  for (int i = 0; i < dataInTemp1.length; i++) {
    dataIn1[i] = int(dataInTemp1[i]);
  }
  String[] dataInTemp = split(data, ",");
  dataIn = new int[dataInTemp.length];
  for (int i = 0; i < dataInTemp.length; i++) {
    dataIn[i] = int(dataInTemp[i]);
  }
}

void baudratelistFunction(int index) {
  String baudstring;
  baudstring = baudlist.getItem(index).get("name").toString();
  selectedbaudrate = Integer.parseInt(baudstring);
  println("Selected", selectedbaudrate);
}
void comportlistFunction(int index) {
  selectedport = portlist.getItem(index).get("name").toString();
  println("Selected", selectedport);
}
void connectButtonFunction() {
  if (!connectButtonStatus) {
    serial = new Serial(this, selectedport, selectedbaudrate);
    connectionButton.setLabel("Disconnect");
    connectButtonStatus = true;
    println("Connected", selectedport, "at", selectedbaudrate);
  } else {
    serial.stop();
    connectionButton.setLabel("Connect");
    connectButtonStatus = false;
    println("Disconnected from", selectedport);
  }
}
void baudratelistFunction1(int index) {
  String baudstring1;
  baudstring1 = baudlist1.getItem(index).get("name").toString();
  selectedbaudrate1 = Integer.parseInt(baudstring1);
  println("Selected", selectedbaudrate1);
}
void comportlistFunction1(int index) {
  selectedport1 = portlist1.getItem(index).get("name").toString();
  println("Selected", selectedport1);
}
void connectButtonFunction1() {
  if (!connectButtonStatus1) {
    serial1 = new Serial(this, selectedport1, selectedbaudrate1);
    connectionButton1.setLabel("Disconnect");
    connectButtonStatus1 = true;
    println("Connected", selectedport1, "at", selectedbaudrate1);
  } else {
    serial1.stop();
    connectionButton1.setLabel("Connect");
    connectButtonStatus1 = false;
    println("Disconnected from", selectedport1);
  }
}


void connectionUI(int x, int y) { //Function that creates the connection UI
  toggleConnectionUIButton = cp5.addButton("toggleConnectionUI") //Make button "toggleUI".
    .setLabel("Connection UI")
    .setSize(100, 30)
    .setPosition(x, y);
  y=y+50;
  connectionButton = cp5.addButton("connectButtonFunction")
    .setLabel("Connect")
    .setSize(70, 30)
    .setPosition(x, y);

  portlist = cp5.addScrollableList("comportlistFunction")
    .setLabel("select port")
    .setBarHeight(30)
    .setPosition(x+100, y)
    .setItemHeight(25);

  baudlist = cp5.addScrollableList("baudratelistFunction")
    .setLabel("select baudrate")
    .setBarHeight(30)
    .setPosition(x+220, y)
    .setItemHeight(24);

  baudlist.addItem("9600", 9600);
  baudlist.addItem("19200", 19200);
  baudlist.addItem("38400", 38400);
  baudlist.addItem("57600", 57600);
  baudlist.addItem("115200", 115200);

  receivedArea = cp5.addTextarea("receivedData")
    .setSize(360, 140)
    .setPosition(x, y+250)
    .setColorBackground(80);
  arduinoConsole = cp5.addConsole(receivedArea);
  x = x+400;
  connectionButton1 = cp5.addButton("connectButtonFunction1")
    .setLabel("Connect")
    .setSize(70, 30)
    .setPosition(x, y);

  portlist1 = cp5.addScrollableList("comportlistFunction1")
    .setLabel("select port")
    .setBarHeight(30)
    .setPosition(x+100, y)
    .setItemHeight(25);

  baudlist1 = cp5.addScrollableList("baudratelistFunction1")
    .setLabel("select baudrate")
    .setBarHeight(30)
    .setPosition(x+220, y)
    .setItemHeight(24);

  baudlist1.addItem("9600", 9600);
  baudlist1.addItem("19200", 19200);
  baudlist1.addItem("38400", 38400);
  baudlist1.addItem("57600", 57600);
  baudlist1.addItem("115200", 115200);

  receivedArea1 = cp5.addTextarea("receivedData1")
    .setSize(360, 140)
    .setPosition(x, y+250)
    .setColorBackground(80);
  arduinoConsole1 = cp5.addConsole(receivedArea1);

  String[] availableports = Serial.list(); //   <-------------------- Søren explain plz
  for (int i = 0; i < availableports.length; i++) {
    portlist.addItem(availableports[i], availableports[i]);
    portlist1.addItem(availableports[i], availableports[i]);
  }

  connectionButton.setVisible(false);
  portlist.setVisible(false);
  baudlist.setVisible(false);
  receivedArea.setVisible(false);
  connectionButton1.setVisible(false);
  portlist1.setVisible(false);
  baudlist1.setVisible(false);
  receivedArea1.setVisible(false);
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
  dataOut[0] = 1;
  sendData();
  dataOut[0] = 0;
}

void sub1ButtonFunction() {
  dataOut[1] = 1;
  sendData();
  dataOut[1] = 0;
}

void add05ButtonFunction() {
  dataOut[2] = 1;
  sendData();
  dataOut[2] = 0;
}

void sub05ButtonFunction() {
  dataOut[3] = 1;
  sendData();
  dataOut[3] = 0;
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
