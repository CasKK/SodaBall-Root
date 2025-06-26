class Connection {

  PApplet parent;
  ControlP5 cp5;
  Serial serial, serial1;
  Textarea receivedArea, receivedArea1;
  Println arduinoConsole, arduinoConsole1;
  Button connectionButton, connectionButton1;
  ScrollableList portlist, portlist1;
  ScrollableList baudlist, baudlist1;
  boolean connectButtonStatus = false;
  boolean connectButtonStatus1 = false;
  String selectedport, selectedport1;
  int selectedbaudrate, selectedbaudrate1;
  int id;


  Connection(PApplet p, ControlP5 cp, int id_) {
    parent = p;
    cp5 = cp;
    id = id_;
    makeUI(20 + 800 * id, 40);
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
    //baudlist.setVisible(false);

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
    //baudlist1.setVisible(false);

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
      serial1 = new Serial(parent, selectedport1, selectedbaudrate);
      connectionButton1.setLabel("Disconnect");
      connectButtonStatus1 = true;
      println("Connected", selectedport1, "at", selectedbaudrate);
    } else {
      serial1.stop();
      connectionButton1.setLabel("Connect");
      connectButtonStatus1 = false;
      println("Disconnected from", selectedport1);
    }
  }
}
