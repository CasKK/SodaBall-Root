class Connection {

  PApplet parent;
  ControlP5 cp5;
  Team parentTeam;
  Serial serial;
  Textarea receivedArea;
  Println arduinoConsole;
  Button connectionButton;
  ScrollableList portlist;
  ScrollableList baudlist;
  boolean connectButtonStatus = false;
  String selectedport;
  int selectedbaudrate;
  int id;
  String[] messageArrayOut = {};
  String[] messageArrayIn = {};


  Connection(PApplet p, ControlP5 cp, int id_, int x, int y, Team t) {
    parent = p;
    cp5 = cp;
    id = id_;
    makeUI(x, y);
    parentTeam = t;
  }


  public void sendData(String message) {
    try {
      serial.write(message);
      serial.write(10);
      messageArrayOut = append(messageArrayOut, message);
    }
    catch (Exception e) {
      println("Serial port error: " + e.getMessage());
    }
  }


  public int[] readData() {
    final int[] defaultData = new int[12]; // all zeros by default

    if (serial == null || serial.available() <= 0) {
      return null;
    }

    try {
      String data = serial.readStringUntil('\n');
      if (data != null) {
        data = data.trim(); // Clean up trailing newline or whitespace
        receivedArea.setText("Arduino: " + data);
        messageArrayIn = append(messageArrayIn, data + nf(millis()));

        String[] tokens = split(data, ",");
        if (tokens.length != 12) return null;

        int[] parsed = new int[tokens.length];

        for (int i = 0; i < tokens.length; i++) {
          parsed[i] = int(trim(tokens[i])); // Trim in case of trailing spaces
        }
        return parsed;
      }
    }
    catch (Exception e) {
      println("Serial port error: " + e.getMessage());
    }

    return null;
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
      parentTeam.firstConnectedTime = millis();
      parentTeam.triggerAllowed = false;
    } else {
      serial.stop();
      connectionButton.setLabel("Connect");
      connectButtonStatus = false;
      println("Disconnected from", selectedport);
    }
  }
}
