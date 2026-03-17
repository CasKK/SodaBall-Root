import serial
import serial.tools.list_ports
import crcmod
import time
from collections import deque
from collections import OrderedDict
import threading
import pygame
from pathlib import Path
import random
from pygame._sdl2.video import Window
import os

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
        self.score = {1: 0, 2: 0}
        self.money = {1: 0, 2: 0}
        self.nodes = {}

        self.airOwner = None  # node_id that owns the current air sequence
        self.airDuration = 10.0        # total air time
        self.smokeStartDelay = 1.0   # seconds after air starts
        self.smokeDuration = 5.0     # seconds before air ends
        self.nosmokeDuration = 3.0
        self.airCost = 20
        self.bigCoin = 20
        self.smallCoin = 10
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
        if button == "Air" and self.airPhase == "IDLE" and self.money[node_id] >= self.airCost:
            self.airOwner = node_id
            self.airPhase = "AIR"
            self.airStart = time.time()
            self.money[node_id] -= self.airCost
            node = self.nodes.get(node_id)
            if node and node.is_ready():
                node.send_command("R", "air")
                node.send_command("D", self.money[node_id])
            if debug: print(f"R, air → node {node_id}")

        elif button == "coinBig":
            n = self.nodes.get(node_id)
            if n and n.is_ready():
                self.money[node_id] += 20
                n.send_command("D", self.money[node_id])
                if debug: print("D, +bigCoin")

        elif button == "coinSmall":
            n = self.nodes.get(node_id)
            if n and n.is_ready():
                self.money[node_id] += 10
                n.send_command("D", self.money[node_id])
                if debug: print("D, +smallCoin")
            

    def handle_goal(self, scoring_node, side):
        if scoring_node == 1:
            self.score[2] += 1
        else:
            self.score[1] += 1

        if debug: print(f"Goal registered in {scoring_node}'s net! Score is now {self.score[1]} : {self.score[2]}")
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
        elif self.airPhase == "SMOKE" and elapsed >= (self.airDuration - self.smokeDuration):
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

        # Jump to the *start* of NOSMOKE
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

threading.Thread(target=console_loop, args=(controller,), daemon=True).start()

def game_loop():
    while True:
        manager.update()
        for node in list(manager.nodes_by_port.values()):
            node.poll()
        controller.checkStates()
        time.sleep(0.01)

threading.Thread(target=game_loop, daemon=True).start()

###### File path stuff ######
BASE_DIR = Path(__file__).resolve().parent
def asset_path(*parts):
    return BASE_DIR.joinpath("Figures_and_Fonts", *parts)

###### Monitor setup ######
pygame.init()

desktop_sizes = pygame.display.get_desktop_sizes()
print("Desktop sizes:", desktop_sizes)

if len(desktop_sizes) < 2:
    raise RuntimeError("Two monitors required for dual display mode.")

LEFT_WIDTH, LEFT_HEIGHT = desktop_sizes[0]
RIGHT_WIDTH, RIGHT_HEIGHT = desktop_sizes[1]

if LEFT_HEIGHT != RIGHT_HEIGHT:
    raise RuntimeError("Monitor heights must match for spanning mode.")

TOTAL_WIDTH = LEFT_WIDTH + RIGHT_WIDTH
TOTAL_HEIGHT = LEFT_HEIGHT

# Create one spanning borderless window
window = Window(
    "SodaBall",
    size=(TOTAL_WIDTH, TOTAL_HEIGHT)
)
window.borderless = True
surface = window.get_surface()

SCALE_FACTOR = 1
if LEFT_HEIGHT == 270:
    LAST_SCALE_FACTOR = 1
elif LEFT_HEIGHT == 540:
    LAST_SCALE_FACTOR = 2
elif LEFT_HEIGHT == 1080:
    LAST_SCALE_FACTOR = 4
elif LEFT_HEIGHT == 2160:
    LAST_SCALE_FACTOR = 8
else:
    raise RuntimeError("Unsupported resolution. Suppoorted resolutions: 540p, 1080p, 4k.", desktop_sizes)

# ---------------------------
# Assets
# ---------------------------

bane_img = pygame.transform.scale_by(
    pygame.image.load(asset_path("Bane.png")).convert(),SCALE_FACTOR) # Source image is 480x270

BASE_WIDTH = bane_img.get_width()
BASE_HEIGHT = bane_img.get_height()

money_cover = pygame.transform.scale_by(
    pygame.image.load(asset_path("moneycover.png")).convert(), SCALE_FACTOR) # Source image is 236x41

score_coverL = pygame.transform.scale_by(
    pygame.image.load(asset_path("scorecoverL.png")).convert(), SCALE_FACTOR) # Source image is 152x229
score_coverR = pygame.transform.scale_by(
    pygame.image.load(asset_path("scorecoverR.png")).convert(), SCALE_FACTOR) # Source image is 152x229

wind_img = pygame.transform.scale_by(
    pygame.image.load(asset_path("Wind.png")).convert_alpha(), # Source image is 32x32
    (2*SCALE_FACTOR, 2*SCALE_FACTOR) # double size to match the screen size of other assets
)
wind_img1 = pygame.transform.flip(wind_img, True, False)

windsock_frames = [
    pygame.transform.scale_by(pygame.image.load(asset_path(f"pixilart_windsock/windsock_{i+1}.png")).convert_alpha(),SCALE_FACTOR) # Source image is 123x102
    for i in range(4)]
windsock_frames1 = [pygame.transform.flip(f, True, False) for f in windsock_frames]

profile_pictures = [
    pygame.transform.scale(
        pygame.image.load(asset_path(f"Profiles/profile_img_{i+1}.jpg")).convert_alpha(),
        (75*SCALE_FACTOR, 75*SCALE_FACTOR)
    )
    for i in range(2)
]

# Fonts
font = pygame.font.Font(asset_path("Press_Start_2P/PressStart2P-Regular.ttf"), 30*SCALE_FACTOR)
scoreFont = pygame.font.Font(asset_path("digital_7/digital-7.ttf"), 250*SCALE_FACTOR)

RED = (220, 0, 0)

# ---------------------------
# Internal render surface
# ---------------------------
render_surface = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
render_surface0 = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))


# ---------------------------
# Wind particles
# ---------------------------
# Wind configuration
WIND_COUNT = 200
WIND_SPEED_MIN = 300 * SCALE_FACTOR
WIND_SPEED_MAX = 500 * SCALE_FACTOR
WIND_WIDTH = 10 * SCALE_FACTOR
WIND_HEIGHT = 2 * SCALE_FACTOR
AIR_DIRECTION = "right"
show_air = False

class WindEffect:
    def __init__(self, mirror=False):
        self.mirror = mirror
        self.reset()

    def _direction(self):
        d = controller.airOwner
        if self.mirror:
            return 2 if d == 1 else 1  # flip it
        return d

    def reset(self):
        self.y = random.randint(0, BASE_HEIGHT)
        self.speed = random.uniform(WIND_SPEED_MIN, WIND_SPEED_MAX)
        if self._direction() == 1:
            self.x = random.randint(-BASE_WIDTH, 0)
        else:
            self.x = random.randint(BASE_WIDTH, BASE_WIDTH * 2)

    def update(self, dt):
        if self._direction() == 1:
            self.x += self.speed * dt
            if self.x > BASE_WIDTH:
                self.reset()
        else:
            self.x -= self.speed * dt
            if self.x < -WIND_WIDTH:
                self.reset()

    def draw(self, surface):
        pygame.draw.rect(surface, (200, 200, 200),
                         (int(self.x), int(self.y), WIND_WIDTH, WIND_HEIGHT))

wind  = [WindEffect() for _ in range(WIND_COUNT)]
wind0 = [WindEffect(True) for _ in range(WIND_COUNT)]

# ---------------------------
# Cached score rendering and more
# ---------------------------
last_score_1 = None
last_score_2 = None
score_text_1 = None
score_text_2 = None
score_surface1L = pygame.Surface((score_coverL.get_width(), score_coverL.get_height()))
score_surface1R = pygame.Surface((score_coverR.get_width(), score_coverR.get_height()))
score_surface2L = pygame.Surface((score_coverL.get_width(), score_coverL.get_height()))
score_surface2R = pygame.Surface((score_coverR.get_width(), score_coverR.get_height()))
last_money_1 = None
last_money_2 = None
money_text_1 = None
money_text_2 = None
#background_surface = None
background_surface1 = None
background_surface2 = None

clock = pygame.time.Clock()
running = True

profile_pictures_number1 = 0

last_windsock_frame_index = -1

reset = True
windsockReset = True
score_change = False

button_rect = pygame.Rect(10 + 920, 195, 600, 600)

# ==========================================================
# Main loop
# ==========================================================
while running:
    start = time.perf_counter()
    dt = clock.tick(30) / 1000.0
    for event in pygame.event.get(): ######## Input logic
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left mouse button
                if button_rect.collidepoint(event.pos):
                    print("Button clicked")
                    if profile_pictures_number1 <= 2:
                        profile_pictures_number1 = 0
                    else:
                        profile_pictures_number1 += 1
                    reset = True

    # ---------------------------
    # Render base scene
    # ---------------------------
    if reset:
        if debug: print("Base blit")
        #background_surface = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        background_surface1 = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        background_surface2 = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        #background_surface.blit(bane_img, (0, 0))
        background_surface1.blit(bane_img, (0, 0))
        background_surface2.blit(bane_img, (0, 0))

        # Profiles
        background_surface1.blit(profile_pictures[profile_pictures_number1], (5*SCALE_FACTOR, 98*SCALE_FACTOR))
        background_surface1.blit(profile_pictures[1], (BASE_WIDTH - profile_pictures[1].get_width() - 5*SCALE_FACTOR, 98*SCALE_FACTOR))
        background_surface2.blit(profile_pictures[profile_pictures_number1], (BASE_WIDTH - profile_pictures[1].get_width() - 5*SCALE_FACTOR, 98*SCALE_FACTOR))
        background_surface2.blit(profile_pictures[1], (5*SCALE_FACTOR, 98*SCALE_FACTOR))

        reset = False
        reset1 = True # To finish reset while avoiding race condition.


    # Money
    current_money_1 = int(controller.money[1])
    current_money_2 = int(controller.money[2])
    
    if current_money_1 != last_money_1 or reset1:
        background_surface1.blit(money_cover, (2*SCALE_FACTOR,0))
        background_surface2.blit(money_cover, (BASE_WIDTH - money_cover.get_width() - 2*SCALE_FACTOR,0))
        background_surface1.blit(wind_img1,(int(BASE_WIDTH/12), -10*SCALE_FACTOR))
        background_surface2.blit(wind_img,(int(BASE_WIDTH - BASE_WIDTH/12 - wind_img.get_width()), -10*SCALE_FACTOR))
        money_text_1 = font.render(f"{int(controller.money[1]/20)}", True, RED)
        background_surface1.blit(money_text_1, (int(BASE_WIDTH/50), 8*SCALE_FACTOR))
        background_surface2.blit(money_text_1,(int(BASE_WIDTH - (BASE_WIDTH/50 + money_text_1.get_width())), 8*SCALE_FACTOR))
        last_money_1 = current_money_1
    
    if current_money_2 != last_money_2 or reset1:
        background_surface2.blit(money_cover, (2*SCALE_FACTOR,0))
        background_surface1.blit(money_cover, (BASE_WIDTH - money_cover.get_width() - 2*SCALE_FACTOR,0))
        background_surface2.blit(wind_img1,(int(BASE_WIDTH/12), -10*SCALE_FACTOR))
        background_surface1.blit(wind_img,(int(BASE_WIDTH - BASE_WIDTH/12 - wind_img.get_width()), -10*SCALE_FACTOR))
        money_text_2 = font.render(f"{int(controller.money[2]/20)}", True, RED)
        background_surface1.blit(money_text_2,(int(BASE_WIDTH - (BASE_WIDTH/50 + money_text_2.get_width())), 8*SCALE_FACTOR))
        background_surface2.blit(money_text_2, (int(BASE_WIDTH/50), 8*SCALE_FACTOR))
        last_money_2 = current_money_2

    
    # Score
    current_score_1 = int(controller.score[1])
    current_score_2 = int(controller.score[2])

    if current_score_1 != last_score_1 or reset1:
        score_surface1L.blit(score_coverL, (0,0))
        score_surface1R.blit(score_coverR, (0,0))
        score_text_1 = scoreFont.render(str(current_score_1), True, RED)
        score_height = 94 * SCALE_FACTOR - (score_text_1.get_height() // 2)
        score_surface1L.blit(score_text_1, (0, score_height))
        score_surface1R.blit(score_text_1, (152 * SCALE_FACTOR - score_text_1.get_width(), score_height))
        background_surface1.blit(score_surface1L, (88 * SCALE_FACTOR, 41 * SCALE_FACTOR))
        background_surface2.blit(score_surface1R, (BASE_WIDTH//2,41*SCALE_FACTOR))
        score_change = True # Because windsock and score interfere.
        last_score_1 = current_score_1

    if current_score_2 != last_score_2 or reset1:
        score_surface2L.blit(score_coverL, (0,0))
        score_surface2R.blit(score_coverR, (0,0))
        score_text_2 = scoreFont.render(str(current_score_2), True, RED)
        score_height = 94 * SCALE_FACTOR - (score_text_2.get_height() // 2)
        score_surface2R.blit(score_text_2, (152 * SCALE_FACTOR - score_text_2.get_width(), score_height))
        score_surface2L.blit(score_text_2, (0, score_height))
        background_surface1.blit(score_surface2R, (BASE_WIDTH//2,41*SCALE_FACTOR))
        background_surface2.blit(score_surface2L, (88 * SCALE_FACTOR, 41 * SCALE_FACTOR))
        score_change = True # Because windsock and score interfere.
        last_score_2 = current_score_2
        reset1 = False # To reset while avoiding race condition


    # Wind
    air_phase = controller.airPhase
    air_owner = controller.airOwner

    if air_phase != "IDLE":
        frame_index = (pygame.time.get_ticks() // 100) % len(windsock_frames)
        if frame_index != last_windsock_frame_index or score_change:
        # Windsock
            AIR_DIRECTION = "right" if air_owner == 1 else "left"
            show_air = True
            
            background_surface1.blit(score_surface1L, (88 * SCALE_FACTOR, 41 * SCALE_FACTOR))
            background_surface2.blit(score_surface1R, (BASE_WIDTH//2,41*SCALE_FACTOR))
                
            background_surface1.blit(score_surface2R, (BASE_WIDTH//2,41*SCALE_FACTOR))
            background_surface2.blit(score_surface2L, (88 * SCALE_FACTOR, 41 * SCALE_FACTOR))

            if air_owner == 1:
                background_surface1.blit(windsock_frames[frame_index],(178*SCALE_FACTOR, 168*SCALE_FACTOR))
                background_surface2.blit(windsock_frames1[frame_index], (178*SCALE_FACTOR, 168*SCALE_FACTOR))
            else:
                background_surface2.blit(windsock_frames[frame_index],(178*SCALE_FACTOR, 168*SCALE_FACTOR))
                background_surface1.blit(windsock_frames1[frame_index],(178*SCALE_FACTOR, 168*SCALE_FACTOR))
            
            
            last_windsock_frame_index = frame_index
            score_change = False # Because windsock and score interfere.
    else:
        if last_windsock_frame_index != -1:
            print("place")
            #blit empty windsock backbround (score_surfaceXX) or reset
            reset = True
            last_windsock_frame_index = -1
        show_air = False

    render_surface.blit(background_surface1, (0, 0))
    render_surface0.blit(background_surface2, (0, 0))
    
    if show_air:
        for particle in wind:
            particle.update(dt)
            particle.draw(render_surface)
        for particle in wind0:
            particle.update(dt)
            particle.draw(render_surface0)

    # Scale base render to monitor size
    scaled_left = pygame.transform.scale_by(render_surface, LAST_SCALE_FACTOR)
    scaled_right = pygame.transform.scale_by(render_surface0, LAST_SCALE_FACTOR)

    # Draw both halves into spanning window
    surface.blit(scaled_left, (0, 0))
    surface.blit(scaled_right, (LEFT_WIDTH, 0))
    window.flip()
    print(time.perf_counter() - start)

pygame.quit()