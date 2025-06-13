class Team {


  PApplet parent;
  ControlP5 cp5;
  Serial serial, serial1;
  Textarea receivedArea, receivedArea1;
  Println arduinoConsole, arduinoConsole1;
  Button connectionButton, connectionButton1;
  Button goalButton, add05Button, sub1Button, add1Button;
  ScrollableList portlist, portlist1;
  ScrollableList baudlist, baudlist1;
  boolean connectButtonStatus = false;
  boolean connectButtonStatus1 = false;
  String selectedport, selectedport1;
  int selectedbaudrate, selectedbaudrate1;
  int[] dataOut = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  int[] dataIn = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  int[] lastDataIn = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  String[] messageArrayOut = {}; //Not in use
  String[] messageArrayIn = {}; //Not in use
  int id;
  int rounds = 0;
  boolean goalMode = false;
  boolean soundStarted = false;
  double goalModeStartTime;
  int goalTime = 15000; //Unit: ms

  Team(PApplet p, ControlP5 cp, int id_) {
    parent = p;
    cp5 = cp;
    id = id_;
    makeUI(20 + 800 * id, 40);
    editUI(420 + 800 * id, 40);
  }

  void makeUI(int x, int y) {
    connectionButton = cp5.addButton("connectButtonFunction" + id)
      .setLabel("Connect")
      .setSize(70, 30)
      .setPosition(x, y)
      .onClick(e -> connectButtonFunction());

    portlist = cp5.addScrollableList("comportlistFunction" + id)
      .setLabel("select port")
      .setBarHeight(30)
      .setPosition(x+100, y)
      .setItemHeight(25);
    portlist.onChange(e -> {
      float val = e.getController().getValue();
      comportlistFunction((int) val);
    }
    );

    baudlist = cp5.addScrollableList("baudratelistFunction" + id)
      .setLabel("select baudrate")
      .setBarHeight(30)
      .setPosition(x+220, y)
      .setItemHeight(24);
    baudlist.onChange(e -> {
      float val = e.getController().getValue();
      baudratelistFunction((int) val);
    }
    );

    baudlist.addItem("9600", 9600);
    baudlist.addItem("19200", 19200);
    baudlist.addItem("38400", 38400);
    baudlist.addItem("57600", 57600);
    baudlist.addItem("115200", 115200);

    receivedArea = cp5.addTextarea("receivedData" + id)
      .setSize(360, 140)
      .setPosition(x, y+250)
      .setColorBackground(80);
    arduinoConsole = cp5.addConsole(receivedArea);

    y = y + 400;

    connectionButton1 = cp5.addButton("connectButtonFunction1" + id)
      .setLabel("Connect")
      .setSize(70, 30)
      .setPosition(x, y)
      .onClick(e -> connectButtonFunction1());

    portlist1 = cp5.addScrollableList("comportlistFunction1" + id)
      .setLabel("select port")
      .setBarHeight(30)
      .setPosition(x+100, y)
      .setItemHeight(25);
    portlist1.onChange(e -> {
      float val = e.getController().getValue();
      comportlistFunction1((int) val);
    }
    );

    baudlist1 = cp5.addScrollableList("baudratelistFunction1" + id)
      .setLabel("select baudrate")
      .setBarHeight(30)
      .setPosition(x+220, y)
      .setItemHeight(24);
    baudlist1.onChange(e -> {
      float val = e.getController().getValue();
      baudratelistFunction1((int) val);
    }
    );

    baudlist1.addItem("9600", 9600);
    baudlist1.addItem("19200", 19200);
    baudlist1.addItem("38400", 38400);
    baudlist1.addItem("57600", 57600);
    baudlist1.addItem("115200", 115200);

    receivedArea1 = cp5.addTextarea("receivedData1" + id)
      .setSize(360, 140)
      .setPosition(x, y+250)
      .setColorBackground(80);
    arduinoConsole1 = cp5.addConsole(receivedArea1);

    String[] availableports = Serial.list();
    for (int i = 0; i < availableports.length; i++) {
      portlist.addItem(availableports[i], availableports[i]);
      portlist1.addItem(availableports[i], availableports[i]);
    }
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
    }
    catch (Exception e) {
      println("Serial port error: " + e.getMessage());
    }
  }


  public void readData() {
    String data = "";
    if (serial != null) {
      try {
        if (serial.available() > 0) {
          data = serial.readStringUntil(10);
          if (data != null) {
            receivedArea.setText("Arduino: " + data);
            messageArrayIn = append(messageArrayIn, data);

            String[] dataInTemp = split(data, ",");
            dataIn = new int[dataInTemp.length];
            for (int i = 0; i < dataInTemp.length; i++) {
              dataIn[i] = int(dataInTemp[i]);
            }
          }
        }
      }
      catch (Exception e) {
        println("Serial port error: " + e.getMessage());
      }
    }
  }

  public void updateValues() {
    boolean shouldSend = false;

    if (dataIn[0] == 1) {
      rounds += bigCoinAirValue;
      shouldSend = true;
      dataIn[0] = 0;
    }

    if (dataIn[1] == 1) {
      rounds += smallCoinAirValue;
      shouldSend = true;
      dataIn[1] = 0;
    }

    if (dataIn[2] == 1) {
      if (!airOn && rounds >= airThesholdValue) {
        rounds -= bigCoinAirValue;
        dataOut[5] = 1;
        airOnFunction();
        smokeTeamId = id;
        smokeOnFunction(id);

        shouldSend = true;
      }
      dataIn[2] = 0;
    }

    if (dataIn[3] == 1) {
      //if (goalMode) goalMode = false;
      if (!goalMode) {
        soundTeamA.stop();
        soundTeamB.stop();
        teamB.goalMode = false;
        teamA.goalMode = false;
      }
      goalFunction();
      dataIn[3] = 0;
      // Future logic can go here
    }

    if (shouldSend) {
      dataOut[4] = rounds;
      sendData();
    }
  }

  void goalFunction() {
    if (!goalMode) {
      goalMode = true;
      goalModeStartTime = millis();
      soundStarted = false;
    }
    if (goalMode) {
      if (!soundStarted) {
        soundStarted = true;
        reduceOtherVolumes();
        if (id == 0)soundTeamA.play();
        if (id == 1)soundTeamB.play();
      }
      fill(255, 0, 0);
      rect(100 + 800 * id, 100, 100, 100);
    }
    if (millis() >= goalModeStartTime + goalTime) {
      soundTeamA.stop();
      soundTeamB.stop();
      restoreOtherVolumes();
      goalMode = false;
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
      serial = new Serial(parent, selectedport, selectedbaudrate);
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
    String baudstring;
    baudstring = baudlist1.getItem(index).get("name").toString();
    selectedbaudrate1 = Integer.parseInt(baudstring);
    println("Selected", selectedbaudrate1);
  }
  void comportlistFunction1(int index) {
    selectedport1 = portlist1.getItem(index).get("name").toString();
    println("Selected", selectedport1);
  }
  void connectButtonFunction1() {
    if (!connectButtonStatus1) {
      serial1 = new Serial(parent, selectedport1, selectedbaudrate1);
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
  void editUI(int x, int y) {
    add1Button = cp5.addButton("add1ButtonFunction" + id)
      .setLabel("+1")
      .setSize(60, 30)
      .setPosition(x, y)
      .onClick(e -> add1ButtonFunction());
    sub1Button = cp5.addButton("sub1ButtonFunction" + id)
      .setLabel("air")
      .setSize(60, 30)
      .setPosition(x + 70, y)
      .onClick(e -> sub1ButtonFunction());
    add05Button = cp5.addButton("add05ButtonFunction" + id)
      .setLabel("+.5")
      .setSize(60, 30)
      .setPosition(x, y + 40)
      .onClick(e -> add05ButtonFunction());
    goalButton = cp5.addButton("goalButtonFunction" + id)
      .setLabel("GOAL")
      .setSize(60, 30)
      .setPosition(x + 70, y + 40)
      .onClick(e -> goalButtonFunction());
  }
  void add1ButtonFunction() {
    dataIn[0] = 1;
  }

  void sub1ButtonFunction() {
    dataIn[2] = 1;
  }

  void add05ButtonFunction() {
    dataIn[1] = 1;
  }

  void goalButtonFunction() {
    dataIn[3] = 1;
  }
  
  void reduceOtherVolumes() {
  try {
    //Runtime.getRuntime().exec("C:\\Program Files\\NirSoft\\nircmd.exe setappvolume spotify.exe 0.2");
    Runtime.getRuntime().exec("C:\\Program Files\\NirSoft\\nircmd.exe setappvolume chrome.exe 0.2");
    // Add more apps as needed
  } catch (IOException e) {
    e.printStackTrace();
  }
}

void restoreOtherVolumes() {
  try {
    //Runtime.getRuntime().exec("C:\\Program Files\\NirSoft\\nircmd.exe setappvolume spotify.exe 1.0");
    Runtime.getRuntime().exec("C:\\Program Files\\NirSoft\\nircmd.exe setappvolume chrome.exe 1.0");
  } catch (IOException e) {
    e.printStackTrace();
  }
}

  
}
