import serial
import crcmod
import time
from collections import deque
from collections import OrderedDict

crc8 = crcmod.predefined.mkCrcFun('crc-8')
RETRY_INTERVAL = 0.2   # seconds
MAX_SEEN = 100
debug = True

class ArduinoNode:
    def __init__(self, port, arduino_id, event_callback):
        self.id = arduino_id
        self.event_callback = event_callback

        self.port = port
        self.ser = None
        self.connected = False
        self.last_connect_attempt = 0
        self.connect_interval = 0.5  # seconds

        self.seen = OrderedDict()
        self.cmd_seq = 0
        self.pending = {}
        self.queue = deque()

        self.money = 0

    def connect(self):
        now = time.time()
        if now - self.last_connect_attempt < self.connect_interval:
            return

        self.last_connect_attempt = now
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=0.05)
            self.connected = True
            self.on_connect()
            if debug: print(f"[Node {self.id}] Connected on {self.port}")
        except serial.SerialException:
            self.connected = False

    def disconnect(self):
        if self.connected:
            if debug: print(f"[Node {self.id}] Disconnected")
        self.connected = False
        try:
            if self.ser:
                self.ser.close()
        except serial.SerialException:
            pass
        self.ser = None

    def on_connect(self):
        # Arduino reboot == protocol reset
        self.seen.clear()
        self.pending.clear()
        self.queue.clear()
        self.cmd_seq = 0

    def is_ready(self):
        return self.connected

    def send_ack(self, sender_id, seq):
        body = f"A,{sender_id},{seq},OK"
        crc = crc8(body.encode())
        try:
            self.ser.write(f"${body}*{crc:02X}\n".encode())
        except serial.SerialException:
            self.disconnect()

    def send_command(self, cmd_type, value):
        if not self.connected or not self.ser:
            self.disconnect()
            return
    
        body = f"{cmd_type},{self.id},{self.cmd_seq},{value}"
        frame = f"${body}*{crc8(body.encode()):02X}\n"

        self.pending[self.cmd_seq] = {
            "frame": frame,
            "time": time.time()
        }
        self.queue.append(self.cmd_seq)
        try:
            self.ser.write(frame.encode())
        except serial.SerialException:
            self.disconnect()
            return

        self.cmd_seq += 1

    def process_retries(self):
        if not self.queue:
            return

        seq = self.queue[0]
        entry = self.pending.get(seq)

        if entry and time.time() - entry["time"] > RETRY_INTERVAL:
            try:
                self.ser.write(entry["frame"].encode())
            except serial.SerialException:
                self.disconnect()
                return
            entry["time"] = time.time()

    def poll(self):
        if not self.connected:
            self.connect()
            return

        self.process_retries()

        try:
            raw = self.ser.readline()
        except serial.SerialException:
            self.disconnect()
            return

        line = raw.decode(errors='ignore').strip()
        if line and debug:
            print(line)
        if not line.startswith("$") or "*" not in line:
            return
        
        try:
            body, crc_hex = line[1:].split("*", 1)
            if crc8(body.encode()) != int(crc_hex, 16):
                return
        except ValueError:
            return

        parts = body.split(",")

        if len(parts) < 3:
            return
        try:
            msg_type = parts[0]
            sender_id = int(parts[1])
            seq = int(parts[2])
        except ValueError:
            return
        
        if msg_type == "H":
            self.seen.clear()
            self.pending.clear()
            self.queue.clear()
            self.cmd_seq = 0

            self.event_callback({
                "node": sender_id,
                "type": "HELLO",
                "data": []
            })

            self.send_ack(sender_id, seq)
            return

        # ACK for outgoing commands
        if msg_type == "A":
            if seq in self.pending:
                del self.pending[seq]
            if self.queue and self.queue[0] == seq:
                self.queue.popleft()
            return

        key = (sender_id, seq)
        if key in self.seen:
            self.send_ack(sender_id, seq)
            return
        self.seen[key] = None

        if len(self.seen) > MAX_SEEN:
            self.seen.popitem(last=False)  # removes oldest

        # Dispatch events
        self.handle_event(msg_type, parts, sender_id, seq)

    def handle_event(self, msg_type, parts, sender_id, seq):
        event = {
            "node": sender_id,
            "type": msg_type,
            "data": parts[3:]
        }

        self.event_callback(event)
        self.send_ack(sender_id, seq)


class GameController:
    def __init__(self):
        #self.score = {1: 0, 2: 0}
        self.money = {1: 0, 2: 0}
        self.nodes = {}
        self.airStart = 0
        self.airOn = False
        self.airTime = 5

    def register_node(self, node):
        self.nodes[node.id] = node

    def handle_event(self, event):
        node = event["node"]
        etype = event["type"]
        data = event["data"]

        if etype == "G":
            self.handle_goal(node, data[0])
        elif etype == "B":
            self.handle_button(node, data[0])
        elif etype == "HELLO":
            self.sync_node_state(node)


    def handle_button(self, node, button):
        if button == "Air" and self.airOn == False:
            n = self.nodes.get(node)
            if n and n.connected: ################# is_ready
                n.send_command("R", "air")
                self.airOn = True
                self.airStart = time.time()
                if debug: print("R, air")
        elif button == "coinBig":
            n = self.nodes.get(node)
            if n and n.connected: ################# is_ready
                self.money[node] += 20
                node.send_command("D", self.money[node])
                if debug: print("D, +20")
        elif button == "coinSmall":
            n = self.nodes.get(node)
            if n and n.connected: ################# is_ready
                self.nodes[node].money += 10
                node.send_command("D", self.money[node])
                if debug: print("D, +10")
            
    def handle_goal(self, scoring_node, side):
        opponent = 2 if scoring_node == 1 else 1
        if debug: print(f"awaka {opponent}")
        # Show animation based on side added later

    def checkStates(self):
        if self.airOn and time.time() - self.airStart > self.airTime:
            self.nodes[1].send_command("R", "noair")
            self.nodes[2].send_command("R", "noair")
            if debug: print("all noair")
            self.airOn = False

    def sync_node_state(self, node_id):
        node = self.nodes.get(node_id)
        if not node or not node.connected: ################# is_ready
            return

        # Authoritative replay
        if self.airOn:
            node.send_command("R", "air")
        else:
            node.send_command("R", "noair")
        node.send_command("D", self.money[node_id])
        # Add more state here as your system grows


controller = GameController()

nodes = [
    ArduinoNode("COM5", 1, controller.handle_event),
    ArduinoNode("COM4", 2, controller.handle_event),
]

for node in nodes:
    controller.register_node(node)

while True:
    for node in nodes:
        node.poll()
    controller.checkStates()
    time.sleep(0.005)

