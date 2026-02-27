import serial
import serial.tools.list_ports
import crcmod
import time
from collections import deque
from collections import OrderedDict
import threading

crc8 = crcmod.predefined.mkCrcFun('crc-8')
RETRY_INTERVAL = 0.2   # seconds
MAX_SEEN = 100
debug = True


class PortProbe:
    def __init__(self, port):
        self.port = port
        self.ser = serial.Serial(port, 115200, timeout=0.1)
        self.dead = False

    def poll(self):
        if self.dead:
            return None

        try:
            raw = self.ser.readline()
        except (serial.SerialException, OSError):
            # Port disappeared while probing
            self._kill()
            return None

        if not raw:
            return None

        line = raw.decode(errors="ignore").strip()

        if not line.startswith("$") or "*" not in line:
            return None

        try:
            body, crc_hex = line[1:].split("*", 1)
            parts = body.split(",")
        except ValueError:
            return None

        if parts[0] == "H":
            return int(parts[1])

        return None

    def _kill(self):
        self.dead = True
        try:
            self.ser.close()
        except:
            pass

class NodeManager:
    def __init__(self, controller, required_ids):
        self.controller = controller
        self.required_ids = set(required_ids)
        self.probes = {}
        self.nodes_by_port = {}
        self.discovery_complete = False

        self.scan_interval = 0.5      # seconds
        self.last_scan_time = 0
    
    def update(self):
        now = time.time()

        # Always monitor removals quickly
        self._check_removals()

        # Only scan occasionally
        if now - self.last_scan_time < self.scan_interval:
            return

        self.last_scan_time = now

        # If already complete, don't probe
        if self.discovery_complete:
            return

        missing = self.required_ids - set(self.controller.nodes.keys())
        if not missing:
            print("[DISCOVER] All required nodes found.")
            self.discovery_complete = True
            return

        current_ports = {p.device for p in serial.tools.list_ports.comports()}

        for port in current_ports:
            if port in self.probes or port in self.nodes_by_port:
                continue

            # Only probe USB devices (important!)
            if "ttyUSB" not in port and "ttyACM" not in port:
                continue

            try:
                print(f"[DISCOVER] probing {port}")
                self.probes[port] = PortProbe(port)
            except:
                pass

        # Poll probes
        for port, probe in list(self.probes.items()):
            node_id = probe.poll()

            if probe.dead:
                del self.probes[port]
                continue

            if node_id is None:
                continue

            print(f"[DISCOVER] Node {node_id} found on {port}")

            probe.ser.close()
            del self.probes[port]

            node = ArduinoNode(port, node_id, self.controller.handle_event)
            self.controller.register_node(node)
            self.nodes_by_port[port] = node

    def _check_removals(self):
        current_ports = {p.device for p in serial.tools.list_ports.comports()}

        for port, node in list(self.nodes_by_port.items()):
            if port not in current_ports:
                print(f"[DISCOVER] Node {node.id} removed")
                node.disconnect()
                del self.nodes_by_port[port]
                self.controller.nodes.pop(node.id, None)

                # Restart discovery
                self.discovery_complete = False


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
        except (serial.SerialException, OSError):
            self.connected = False

    def disconnect(self):
        if self.connected:
            if debug: print(f"[Node {self.id}] Disconnected")
        self.connected = False
        try:
            if self.ser:
                self.ser.close()
        except (serial.SerialException, OSError):
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
        except (serial.SerialException, OSError):
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
            print(frame)
            self.ser.write(frame.encode())
        except (serial.SerialException, OSError):
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
            except (serial.SerialException, OSError):
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
        except (serial.SerialException, OSError):
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

        self.airOwner = None  # node_id that owns the current air sequence
        self.airDuration = 10.0        # total air time
        self.smokeStartDelay = 1.0   # seconds after air starts
        self.smokeEndEarly = 5.0     # seconds before air ends
        self.nosmokeDuration = 3.0
        self.airStart = None
        self.airActive = False
        self.airPhase = "IDLE"
        self.smokeActive = False


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


    def handle_button(self, node_id, button):
        if button == "Air" and self.airPhase == "IDLE":
            self.airOwner = node_id
            self.airPhase = "AIR"
            self.airStart = time.time()

            node = self.nodes.get(node_id)
            if node and node.is_ready():
                node.send_command("R", "air")

            if debug: print(f"R, air → node {node_id}")

        elif button == "coinBig":
            n = self.nodes.get(node_id)
            if n and n.is_ready():
                self.money[node_id] += 20
                n.send_command("D", self.money[node_id])
                if debug: print("D, +20")

        elif button == "coinSmall":
            n = self.nodes.get(node_id)
            if n and n.is_ready():
                self.money[node_id] += 10
                n.send_command("D", self.money[node_id])
                if debug: print("D, +10")
            

    def handle_goal(self, scoring_node, side):
        opponent = 2 if scoring_node == 1 else 1
        if debug: print(f"awaka {opponent}")
        # Show animation based on side added later


    def checkStates(self):
        if self.airPhase == "IDLE":
            return

        elapsed = time.time() - self.airStart

        # AIR → SMOKE
        if self.airPhase == "AIR" and elapsed >= self.smokeStartDelay:
            node = self.nodes.get(self.airOwner)
            if node and node.is_ready():
                node.send_command("R", "smoke")
            self.airPhase = "SMOKE"
            print(f"R, smoke → node {self.airOwner}")

        # SMOKE → NOSMOKE
        elif self.airPhase == "SMOKE" and elapsed >= (self.airDuration - self.smokeEndEarly):
            node = self.nodes.get(self.airOwner)
            if node and node.is_ready():
                node.send_command("R", "nosmoke")
            self.airPhase = "NOSMOKE"
            print(f"R, nosmoke → node {self.airOwner}")

        # NOSMOKE → DONE
        elif self.airPhase == "NOSMOKE" and elapsed >= self.airDuration:
            node = self.nodes.get(self.airOwner)
            if node and node.is_ready():
                node.send_command("R", "noair")
            self.airPhase = "IDLE"
            self.airOwner = None
            self.airStart = None
            print("R, noair → done")


    def sync_node_state(self, node_id):
        node = self.nodes.get(node_id)
        if not node or not node.is_ready():
            return

        node.send_command("D", self.money[node_id])
        # Node does NOT own air → force off
        if self.airPhase == "IDLE" or node_id != self.airOwner:
            node.send_command("R", "noair")
            node.send_command("R", "nosmoke")
            return

        # Node owns air → restore correct phase
        node.send_command("R", "air")

        elapsed = time.time() - self.airStart

        if self.airPhase in ("SMOKE",):
            node.send_command("R", "smoke")
        elif self.airPhase in ("NOSMOKE",):
            node.send_command("R", "nosmoke")


    def manual_command(self, cmd):
        parts = cmd.strip().split()
        if not parts:
            return

        op = parts[0].lower()

        try:
            if op == "air":
                self.start_air(int(parts[1]))

            elif op == "noair":
                self.fast_forward_air()

            elif op == "money":
                node_id = int(parts[1])
                delta = int(parts[2])
                self.adjust_money(node_id, delta)

            else:
                print("Unknown command")

        except (IndexError, ValueError):
            print("Invalid command syntax")



    def start_air(self, node_id):
        if self.airPhase != "IDLE":
            return  # ignore or log

        node = self.nodes.get(node_id)
        if not node or not node.is_ready():
            return

        self.airOwner = node_id
        self.airStart = time.time()
        self.airPhase = "AIR"

        node.send_command("R", "air")

        if debug:
            print(f"[MANUAL] air → node {node_id}")
    
    def fast_forward_air(self):
        if self.airPhase not in ("AIR", "SMOKE"):
            return

        node = self.nodes.get(self.airOwner)
        if node and node.is_ready():
            node.send_command("R", "nosmoke")

        # Jump to the *start* of NOSMOKE, not the end
        self.airPhase = "NOSMOKE"
        self.airStart = time.time() - (self.airDuration - self.nosmokeDuration)

        if debug:
            print("[MANUAL] fast-forward → nosmoke (with dwell)")

    
    def adjust_money(self, node_id, delta):
        if node_id not in self.money:
            return

        self.money[node_id] += delta

        node = self.nodes.get(node_id)
        if node and node.is_ready():
            node.send_command("D", self.money[node_id])

        if debug:
            print(f"[MANUAL] money[{node_id}] += {delta} → {self.money[node_id]}")



controller = GameController()
manager = NodeManager(controller, required_ids={1, 2})

def console_loop(controller):
    while True:
        try:
            line = input("> ")
            controller.manual_command(line)
        except EOFError:
            break

threading.Thread(
    target=console_loop,
    args=(controller,),
    daemon=True
).start()

while True:
    manager.update()

    for node in list(manager.nodes_by_port.values()):
        node.poll()

    controller.checkStates()
    time.sleep(0.01)

