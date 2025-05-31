class Team {


  PApplet parent;
  ControlP5 cp5;
  Serial serial;
  Textarea receivedArea;
  Println arduinoConsole;
  Button connectionButton;
  ScrollableList portlist;
  ScrollableList baudlist;
  boolean connectButtonStatus = false;
  String selectedport;
  int selectedbaudrate;
  int[] dataOut = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  int[] dataIn = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  int[] lastDataIn = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  String[] messageArrayOut = {}; //Not in use
  String[] messageArrayIn = {}; //Not in use
  int id;
  int rounds = 0;
  boolean goalMode = false;
  double goalModeStartTime;
  int goalTime = 1000; //Unit: ms

  Team(PApplet p, ControlP5 cp, int id_) {
    parent = p;
    cp5 = cp;
    id = id_;
    makeUI(10 + 400 * id, 160);
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
    String[] availableports = Serial.list();
    for (int i = 0; i < availableports.length; i++) {
      portlist.addItem(availableports[i], availableports[i]);
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
        shouldSend = true;
      }
      dataIn[2] = 0;
    }

    if (dataIn[3] == 1) {
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
    }
    if (goalMode) {
      fill(255, 0, 0);
      rect(100, 100, 100, 100);
      //Toolkit.getDefaultToolkit().beep();
      BEEP.play();
    }
    if (millis() >= goalModeStartTime + goalTime) {
      BEEP.stop();
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
}
