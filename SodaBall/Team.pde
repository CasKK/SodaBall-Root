class Team {

  Connection connection1, connection2;
  PApplet parent;
  ControlP5 cp5;
  Button goalButton, add05Button, sub1Button, add1Button, cancel1Button;
  int[] dataOut = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  int[] dataIn = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  int[] dataIn2 = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  String[] messageArrayOut = {};
  String[] messageArrayIn = {};
  int id;
  int rounds = 0;
  boolean goalMode = false;
  boolean soundStarted = false;
  double goalModeStartTime;
  int goalTime;
  SoundFile sound;

  int connection1Time = 0;
  double lastConnection1Time = 0;
  int connection2Time = 0;
  double lastConnection2Time = 0;
  boolean triggerAllowed = false;
  double firstConnectedTime = 0;

  Team(PApplet p, ControlP5 cp, SoundFile sound_, int id_) {
    parent = p;
    cp5 = cp;
    id = id_;
    editUI(420 + 800 * id, 40);
    sound = sound_;
    goalTime = (int)(sound.duration() * 1000);
    connection1 = new Connection(parent, cp5, id*10, 40 + 800 * id, 40, this);
    connection2 = new Connection(parent, cp5, id*10+1, 40 + 800 * id, 450, this);
  }

  public void sendData() {
    String message = "" ;
    for (int i = 0; i < 12; i++) {
      String messageValue = Integer.toString(dataOut[i]);
      message = message+messageValue;
      if (i<11) message = message + ",";
    }
    connection1.sendData(message);
    connection2.sendData(message);
    //messageArrayOut = append(messageArrayOut, message);
  }


  public void readData() {
  int[] result1 = connection1.readData();
  if (result1 != null) {
    dataIn = result1;
  }

  int[] result2 = connection2.readData();
  if (result2 != null) {
    dataIn2 = result2;
  }

    updateValues();
    updateValues2();
  }

  public void updateValues() {
    boolean shouldSend = false;

    if (!triggerAllowed || connection1.connectButtonStatus == false) {
      if (millis() - firstConnectedTime > 5000) triggerAllowed = true;
      return;
    }

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
    if (dataIn[4] > 0) {
      connection1Time = dataIn[4];
      lastConnection1Time = millis();
    }
    if (dataIn[7] != rounds) {
      shouldSend = true;
    }
    
    //if (dataIn[7] == rounds) {
      parent.fill(0);
      parent.textSize(30);
      parent.text(nf(dataIn[7], 0, 0), 400 + 800 * id, 500);
    //}

    if (shouldSend || dataOut[0] != rounds) {
      dataOut[0] = rounds;
      dataOut[8] = millis();
      dataOut[9] = dataIn[9];
      sendData();
    }
  }

  public void updateValues2() {
    if (dataIn2[4] > 0) {
      connection2Time = dataIn2[4];
      lastConnection2Time = millis();
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
    updateValues();
  }

  void sub1ButtonFunction() {
    dataIn[2] = 1;
    updateValues();
  }

  void add05ButtonFunction() {
    dataIn[1] = 1;
    updateValues();
  }

  void goalButtonFunction() {
    dataIn[3] = 1;
    updateValues();
  }
  void cancel1ButtonFunction() {
    if (rounds >= airThesholdValue) {
      rounds = rounds - airThesholdValue;
    } else {
      rounds = 0;
    }
    updateValues();
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
