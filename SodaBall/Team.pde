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
  int[] dataIn;
  String[] messageArrayOut = {};
  String[] messageArrayIn = {};

  Team(PApplet p, ControlP5 cp) {
    parent = p;
    cp5 = cp;
    makeUI(10, 600);
  }

  void makeUI(int x, int y) {
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
    try {
      while (serial.available() > 0) {
        data = serial.readStringUntil(10);
        if (data != null) {
          receivedArea.setText("Arduino: " + data);
          messageArrayIn = append(messageArrayIn, data);
        }
      }
    }
    catch (Exception e) {
      println("Serial port error: " + e.getMessage());
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
