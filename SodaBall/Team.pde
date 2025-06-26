class Team {

  Connection connection1, connection2;
  PApplet parent;
  ControlP5 cp5;
  Button goalButton, add05Button, sub1Button, add1Button, cancel1Button;
  int[] dataOut = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  int[] dataIn = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  int[] lastDataIn = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  String[] messageArrayOut = {};
  String[] messageArrayIn = {};
  int id;
  int rounds = 0;
  boolean goalMode = false;
  boolean soundStarted = false;
  double goalModeStartTime;
  int goalTime;
  SoundFile sound;

  Team(PApplet p, ControlP5 cp, SoundFile sound_, int id_) {
    parent = p;
    cp5 = cp;
    id = id_;
    editUI(420 + 800 * id, 40);
    sound = sound_;
    goalTime = (int)(sound.duration() * 1000);
    connection1 = new Connection(parent, cp5, id*10, 40 + 800 * id, 40);
    connection2 = new Connection(parent, cp5, id*10+1, 40 + 800 * id, 450);
  }

  public void sendData() {
    try {
      String message = "" ;
      for (int i = 0; i < 12; i++) {
        String messageValue = Integer.toString(dataOut[i]);
        message = message+messageValue;
        if (i<11) message = message + ",";
      }
      connection1.serial.write(message);
      connection1.serial.write(10);
      connection2.serial.write(message);
      connection2.serial.write(10);
      messageArrayOut = append(messageArrayOut, message);
    }
    catch (Exception e) {
      println("Serial port error: " + e.getMessage());
    }
  }


  public void readData() {
    String data = "";
    if (connection1.serial != null) {
      try {
        if (connection1.serial.available() > 0) {
          data = connection1.serial.readStringUntil(10);
          if (data != null) {
            connection1.receivedArea.setText("Arduino: " + data);
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
        rounds -= airThesholdValue;
        dataOut[5] = 1;
        airOnFunction();
        smokeTeamId = id;
        smokeOnFunction(id);

        shouldSend = true;
      }
      dataIn[2] = 0;
    }

    if (dataIn[3] == 1) {
      if (!goalMode) {
        teamA.sound.stop();
        teamB.sound.stop();
        teamB.goalMode = false;
        teamA.goalMode = false;
      }
      goalFunction();
      dataIn[3] = 0;
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
        reduceOtherVolumes();
        sound.play();
        soundStarted = true;
      }
      fill(255, 0, 0);
      rect(100 + 800 * id, 100, 100, 100);
    }
    if (millis() >= goalModeStartTime + goalTime) {
      soundTeamA.stop();
      restoreOtherVolumes();
      goalMode = false;
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
    cancel1Button = cp5.addButton("cancel1ButtonFunction" + id)
      .setLabel("-1")
      .setSize(60, 30)
      .setPosition(x, y + 80)
      .onClick(e -> cancel1ButtonFunction());
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
  void cancel1ButtonFunction() {
    if (rounds >= 5) {
      rounds = rounds - 5;
    } else {
      rounds = 0;
    }
    dataOut[4] = rounds;
    sendData();
  }

  void reduceOtherVolumes() {
    try {
      //Runtime.getRuntime().exec("C:\\Program Files\\NirSoft\\nircmd.exe setappvolume spotify.exe 0.2");
      Runtime.getRuntime().exec("C:\\Program Files\\NirSoft\\nircmd.exe setappvolume chrome.exe 1.0");
    }
    catch (IOException e) {
      e.printStackTrace();
    }
  }

  void restoreOtherVolumes() {
    try {
      //Runtime.getRuntime().exec("C:\\Program Files\\NirSoft\\nircmd.exe setappvolume spotify.exe 1.0");
      Runtime.getRuntime().exec("C:\\Program Files\\NirSoft\\nircmd.exe setappvolume chrome.exe 1.0");
    }
    catch (IOException e) {
      e.printStackTrace();
    }
  }
}
