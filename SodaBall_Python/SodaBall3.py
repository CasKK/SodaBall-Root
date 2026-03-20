import serial
import serial.tools.list_ports
import crcmod
import time
from collections import deque, OrderedDict
import threading
import pygame
from pathlib import Path
import random
from pygame._sdl2.video import Window
import vlc

# ==========================================================
# Constants
# ==========================================================

crc8 = crcmod.predefined.mkCrcFun('crc-8')
RETRY_INTERVAL = 0.2  # seconds
MAX_SEEN = 100
debug = True


# ==========================================================
# PortProbe — identifies an Arduino node on a serial port
# ==========================================================

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
            self._kill()
            return None
        if not raw:
            return None
        line = raw.decode(errors="ignore").strip()
        if not line.startswith("$") or "*" not in line:
            return None
        try:
            body, _ = line[1:].split("*", 1)
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
        except Exception:
            pass


# ==========================================================
# NodeManager — discovers and tracks Arduino nodes
# ==========================================================

class NodeManager:
    def __init__(self, controller, required_ids):
        self.controller = controller
        self.required_ids = set(required_ids)
        self.probes = {}
        self.nodes_by_port = {}
        self.discovery_complete = False
        self.scan_interval = 0.5
        self.last_scan_time = 0

    def update(self):
        now = time.time()
        self._check_removals()

        if now - self.last_scan_time < self.scan_interval:
            return
        self.last_scan_time = now

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
            if "ttyUSB" not in port and "ttyACM" not in port:
                continue
            try:
                print(f"[DISCOVER] Probing {port}")
                self.probes[port] = PortProbe(port)
            except Exception:
                pass

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
                self.discovery_complete = False


# ==========================================================
# ArduinoNode — serial communication with one Arduino
# ==========================================================

class ArduinoNode:
    def __init__(self, port, arduino_id, event_callback):
        self.id = arduino_id
        self.event_callback = event_callback
        self.port = port
        self.ser = None
        self.connected = False
        self.last_connect_attempt = 0
        self.connect_interval = 0.5
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
            if debug:
                print(f"[Node {self.id}] Connected on {self.port}")
        except (serial.SerialException, OSError):
            self.connected = False

    def disconnect(self):
        if self.connected and debug:
            print(f"[Node {self.id}] Disconnected")
        self.connected = False
        try:
            if self.ser:
                self.ser.close()
        except (serial.SerialException, OSError):
            pass
        self.ser = None

    def on_connect(self):
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
        self.pending[self.cmd_seq] = {"frame": frame, "time": time.time()}
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
            self.event_callback({"node": sender_id, "type": "HELLO", "data": []})
            self.send_ack(sender_id, seq)
            return

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
            self.seen.popitem(last=False)

        self.event_callback({"node": sender_id, "type": msg_type, "data": parts[3:]})
        self.send_ack(sender_id, seq)


# ==========================================================
# AudioManager — background music (VLC) + goal celebrations (pygame)
# ==========================================================

class AudioManager:
    CELEBRATE_VOL  = 1.0
    FADE_IN_RATE   = 60.0  # VLC volume units per second (VLC scale: 0–100)
    CHANNEL_CELEBRATE = 1
    VOLUME_NORMAL  = 100   # VLC scale 0–100
    VOLUME_DUCKED  = 15

    def __init__(self, base_dir: Path):
        pygame.mixer.set_num_channels(8)
        self._channel = pygame.mixer.Channel(self.CHANNEL_CELEBRATE)
        self._celebrating = False
        self._current_vol = float(self.VOLUME_NORMAL)

        self._vlc_instance = vlc.Instance("--no-video")
        self._vlc_player = self._vlc_instance.media_player_new()

        # Load per-team celebration sound pools from Audio/teams/<team_id>/
        self._pools: dict[int, list[pygame.mixer.Sound]] = {}
        self._last_played: dict[int, int] = {}
        teams_folder = base_dir / "Audio" / "teams"
        if teams_folder.exists():
            for folder in sorted(teams_folder.iterdir()):
                if folder.is_dir() and folder.name.isdigit():
                    team_id = int(folder.name)
                    sounds = []
                    for f in sorted(folder.iterdir()):
                        if f.suffix.lower() in (".ogg", ".wav", ".mp3"):
                            try:
                                s = pygame.mixer.Sound(str(f))
                                s.set_volume(self.CELEBRATE_VOL)
                                sounds.append(s)
                                print(f"[AUDIO] Loaded team {team_id}: {f.name}")
                            except Exception as e:
                                print(f"[AUDIO] Failed to load {f}: {e}")
                    self._pools[team_id] = sounds
                    self._last_played[team_id] = -1

        # Load background playlist from Audio/background/
        bg_folder = base_dir / "Audio" / "background"
        self._playlist: list[Path] = []
        if bg_folder.exists():
            self._playlist = [
                f for f in bg_folder.iterdir()
                if f.suffix.lower() in (".ogg", ".wav", ".mp3")
            ]
        self._playlist_order: list[Path] = []
        self._current_track: Path | None = None

        if self._playlist:
            self._start_next_track()
        else:
            print("[AUDIO] Warning: no background tracks found in Audio/background/")

    # ── Background music ──────────────────────────────────────────────────────

    def _reshuffle(self):
        new_order = self._playlist.copy()
        random.shuffle(new_order)
        # Avoid replaying the same track immediately after a reshuffle
        if (self._current_track is not None
                and len(new_order) > 1
                and new_order[0] == self._current_track):
            new_order[0], new_order[1] = new_order[1], new_order[0]
        self._playlist_order = new_order

    def _start_next_track(self):
        if not self._playlist_order:
            self._reshuffle()
        track = self._playlist_order.pop(0)
        self._current_track = track
        media = self._vlc_instance.media_new(str(track))
        self._vlc_player.set_media(media)
        self._vlc_player.play()
        self._vlc_player.audio_set_volume(int(self._current_vol))
        print(f"[AUDIO] Now playing: {track.name}")

    # ── Goal celebration ──────────────────────────────────────────────────────

    def play_goal(self, team_id: int):
        pool = self._pools.get(team_id, [])
        if not pool:
            print(f"[AUDIO] No celebration sounds for team {team_id}")
            return

        # Pick a random clip, avoiding immediate repeat
        choices = (
            [i for i in range(len(pool)) if i != self._last_played[team_id]]
            if len(pool) > 1 else [0]
        )
        idx = random.choice(choices)
        self._last_played[team_id] = idx

        if self._channel.get_busy():
            self._channel.stop()

        self._current_vol = float(self.VOLUME_DUCKED)
        self._vlc_player.audio_set_volume(self.VOLUME_DUCKED)
        self._channel.play(pool[idx])
        self._celebrating = True

        if debug:
            print(f"[AUDIO] Goal! team {team_id}, clip {idx + 1}/{len(pool)}")

    # ── Per-frame update (call from main loop) ────────────────────────────────

    def update(self, dt: float):
        # Advance playlist when the current track ends
        state = self._vlc_player.get_state()
        if state in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
            self._start_next_track()

        # Fade background volume back up after celebration finishes
        if self._celebrating and not self._channel.get_busy():
            new_vol = min(self._current_vol + self.FADE_IN_RATE * dt, self.VOLUME_NORMAL)
            self._current_vol = new_vol
            self._vlc_player.audio_set_volume(int(new_vol))
            if new_vol >= self.VOLUME_NORMAL:
                self._celebrating = False
                if debug:
                    print("[AUDIO] Background restored")

    def stop_all(self):
        self._channel.stop()
        self._vlc_player.stop()
        self._vlc_instance.release()


# ==========================================================
# GameController — game state and logic
# ==========================================================

class GameController:
    AIR_DURATION       = 10.0
    SMOKE_START_DELAY  = 1.0
    SMOKE_DURATION     = 5.0
    NOSMOKE_DURATION   = 3.0
    AIR_COST           = 20
    COIN_BIG           = 20
    COIN_SMALL         = 10

    def __init__(self, num_profiles: int):
        self.score  = {1: 0, 2: 0}
        self.money  = {1: 0, 2: 0}
        self.nodes  = {}

        # Maps node_id (1/2) → profile index (0-based) currently displayed
        self.profile_index = {1: 0, 2: 1}
        self.num_profiles  = num_profiles

        # Maps node_id → IRL team_id (1-based, matches Audio/teams/ folder)
        # Kept in sync with profile_index by cycle_profile()
        self.node_team = {1: 1, 2: 2}

        # Air cannon state machine
        self.air_owner  = None
        self.air_start  = None
        self.air_phase  = "IDLE"  # IDLE | AIR | SMOKE | NOSMOKE

        # Thread-safe flag: set by game thread, drained by main/render thread
        self.pending_celebration: int | None = None
        self._celebration_lock = threading.Lock()

    # ── Node registration ─────────────────────────────────────────────────────

    def register_node(self, node):
        self.nodes[node.id] = node

    # ── Profile cycling ───────────────────────────────────────────────────────

    def cycle_profile(self, node_id: int, direction: int):
        """Advance (+1) or reverse (-1) the profile for a node."""
        idx = (self.profile_index[node_id] + direction) % self.num_profiles
        self.profile_index[node_id] = idx
        self.node_team[node_id] = idx + 1  # team IDs are 1-based

    # ── Event dispatch ────────────────────────────────────────────────────────

    def handle_event(self, event):
        etype = event["type"]
        node  = event["node"]
        data  = event["data"]

        if etype == "G":
            self.handle_goal(node, data[0])
        elif etype == "B":
            self.handle_button(node, data[0])
        elif etype == "HELLO":
            self.sync_node_state(node)

    def handle_button(self, node_id, button):
        if (button == "Air"
                and self.air_phase == "IDLE"
                and self.money[node_id] >= self.AIR_COST):
            self.money[node_id] -= self.AIR_COST
            self.air_owner = node_id
            self.air_phase = "AIR"
            self.air_start = time.time()
            node = self.nodes.get(node_id)
            if node and node.is_ready():
                node.send_command("R", "air")
                node.send_command("D", self.money[node_id])
            if debug:
                print(f"R, air → node {node_id}")

        elif button == "coinBig":
            self._add_money(node_id, self.COIN_BIG)

        elif button == "coinSmall":
            self._add_money(node_id, self.COIN_SMALL)

    def handle_goal(self, scoring_node, side):
        """Called when a goal is scored in scoring_node's net."""
        celebrating_node = 2 if scoring_node == 1 else 1
        celebrating_team = self.node_team.get(celebrating_node, celebrating_node)

        if scoring_node == 1:
            self.score[2] += 1
        else:
            self.score[1] += 1

        if debug:
            print(
                f"Goal in node {scoring_node}'s net! "
                f"Score: {self.score[1]}:{self.score[2]} — "
                f"celebrating IRL team {celebrating_team}"
            )

        with self._celebration_lock:
            self.pending_celebration = celebrating_team

    # ── Air cannon state machine ──────────────────────────────────────────────

    def check_air_states(self):
        if self.air_phase == "IDLE":
            return

        elapsed = time.time() - self.air_start

        if self.air_phase == "AIR" and elapsed >= self.SMOKE_START_DELAY:
            self._send_air_command("smoke")
            self.air_phase = "SMOKE"

        elif self.air_phase == "SMOKE" and elapsed >= (self.AIR_DURATION - self.SMOKE_DURATION):
            self._send_air_command("nosmoke")
            self.air_phase = "NOSMOKE"

        elif self.air_phase == "NOSMOKE" and elapsed >= self.AIR_DURATION:
            self._send_air_command("noair")
            self.air_phase = "IDLE"
            self.air_owner = None
            self.air_start = None

    def _send_air_command(self, cmd: str):
        node = self.nodes.get(self.air_owner)
        if node and node.is_ready():
            node.send_command("R", cmd)
        if debug:
            print(f"R, {cmd} → node {self.air_owner}")

    def sync_node_state(self, node_id):
        node = self.nodes.get(node_id)
        if not node or not node.is_ready():
            return
        node.send_command("D", self.money[node_id])
        if self.air_phase == "IDLE" or node_id != self.air_owner:
            node.send_command("R", "noair")
            node.send_command("R", "nosmoke")
            return
        node.send_command("R", "air")
        if self.air_phase == "SMOKE":
            node.send_command("R", "smoke")
        elif self.air_phase == "NOSMOKE":
            node.send_command("R", "nosmoke")

    # ── Money helpers ─────────────────────────────────────────────────────────

    def _add_money(self, node_id: int, amount: int):
        self.money[node_id] += amount
        node = self.nodes.get(node_id)
        if node and node.is_ready():
            node.send_command("D", self.money[node_id])
        if debug:
            print(f"D, money[{node_id}] = {self.money[node_id]}")

    # ── Manual console commands ───────────────────────────────────────────────

    def manual_command(self, cmd: str):
        parts = cmd.strip().split()
        if not parts:
            return
        op = parts[0].lower()
        try:
            if op == "air":
                self._manual_start_air(int(parts[1]))
            elif op == "noair":
                self._manual_fast_forward_air()
            elif op == "money":
                self._add_money(int(parts[1]), int(parts[2]))
            elif op == "goal":
                team = int(parts[1])
                self.score[team] += 1
                with self._celebration_lock:
                    self.pending_celebration = team
                print(f"[MANUAL] Goal team {team}, score: {self.score[1]}:{self.score[2]}")
            else:
                print("Commands: air <node>, noair, money <node> <delta>, goal <team>")
        except (IndexError, ValueError):
            print("Invalid command syntax")

    def _manual_start_air(self, node_id: int):
        if self.air_phase != "IDLE":
            return
        node = self.nodes.get(node_id)
        if not node or not node.is_ready():
            return
        self.air_owner = node_id
        self.air_start = time.time()
        self.air_phase = "AIR"
        node.send_command("R", "air")
        if debug:
            print(f"[MANUAL] air → node {node_id}")

    def _manual_fast_forward_air(self):
        if self.air_phase not in ("AIR", "SMOKE"):
            return
        self._send_air_command("nosmoke")
        self.air_phase = "NOSMOKE"
        self.air_start = time.time() - (self.AIR_DURATION - self.NOSMOKE_DURATION)
        if debug:
            print("[MANUAL] fast-forward → NOSMOKE")


# ==========================================================
# File paths
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

def asset_path(*parts):
    return BASE_DIR.joinpath("Figures_and_Fonts", *parts)


# ==========================================================
# pygame + mixer init
# ==========================================================

pygame.mixer.pre_init(48000, -16, 2, 4096)
pygame.init()

# ==========================================================
# Assets — load before controller so num_profiles is known
# ==========================================================

SCALE_FACTOR = 2

profile_pictures = []
profiles_dir = asset_path("Profiles")
for f in sorted(profiles_dir.iterdir()):
    if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
        profile_pictures.append(
            pygame.transform.scale(
                pygame.image.load(str(f)).convert_alpha(),
                (75 * SCALE_FACTOR, 75 * SCALE_FACTOR)
            )
        )
print(f"[ASSETS] Loaded {len(profile_pictures)} profile pictures")

# ==========================================================
# Bootstrap — controller, manager, audio, threads
# ==========================================================

controller = GameController(num_profiles=len(profile_pictures))
manager    = NodeManager(controller, required_ids={1, 2})
audio      = AudioManager(BASE_DIR)


def console_loop():
    while True:
        try:
            controller.manual_command(input("> "))
        except EOFError:
            break

def game_loop():
    while True:
        manager.update()
        for node in list(manager.nodes_by_port.values()):
            node.poll()
        controller.check_air_states()
        time.sleep(0.01)

threading.Thread(target=console_loop, daemon=True).start()
threading.Thread(target=game_loop,    daemon=True).start()


# ==========================================================
# Monitor setup
# ==========================================================

desktop_sizes = pygame.display.get_desktop_sizes()
print("Desktop sizes:", desktop_sizes)

if len(desktop_sizes) < 2:
    raise RuntimeError("Two monitors required.")

LEFT_WIDTH,  LEFT_HEIGHT  = desktop_sizes[0]
RIGHT_WIDTH, RIGHT_HEIGHT = desktop_sizes[1]

if LEFT_HEIGHT != RIGHT_HEIGHT:
    raise RuntimeError("Monitor heights must match.")

window = Window("SodaBall", size=(LEFT_WIDTH + RIGHT_WIDTH, LEFT_HEIGHT))
window.borderless = True
surface = window.get_surface()

if LEFT_HEIGHT == 540:
    LAST_SCALE_FACTOR = 1
elif LEFT_HEIGHT == 1080:
    LAST_SCALE_FACTOR = 2
elif LEFT_HEIGHT == 2160:
    LAST_SCALE_FACTOR = 4
else:
    raise RuntimeError("Unsupported resolution (540p / 1080p / 4k).", desktop_sizes)


# ==========================================================
# Remaining assets
# ==========================================================

bane_img = pygame.transform.scale_by(
    pygame.image.load(asset_path("Bane.png")).convert(), SCALE_FACTOR)

BASE_WIDTH  = bane_img.get_width()
BASE_HEIGHT = bane_img.get_height()

money_cover  = pygame.transform.scale_by(pygame.image.load(asset_path("moneycover.png")).convert(),  SCALE_FACTOR)
score_coverL = pygame.transform.scale_by(pygame.image.load(asset_path("scorecoverL.png")).convert(), SCALE_FACTOR)
score_coverR = pygame.transform.scale_by(pygame.image.load(asset_path("scorecoverR.png")).convert(), SCALE_FACTOR)

wind_img  = pygame.transform.scale_by(pygame.image.load(asset_path("Wind.png")).convert_alpha(), (2 * SCALE_FACTOR, 2 * SCALE_FACTOR))
wind_img1 = pygame.transform.flip(wind_img, True, False)

windsock_frames  = [
    pygame.transform.scale_by(pygame.image.load(asset_path(f"pixilart_windsock/windsock_{i+1}.png")).convert_alpha(), SCALE_FACTOR)
    for i in range(4)
]
windsock_frames1 = [pygame.transform.flip(f, True, False) for f in windsock_frames]

font      = pygame.font.Font(asset_path("Press_Start_2P/PressStart2P-Regular.ttf"), 30 * SCALE_FACTOR)
fontSmall = pygame.font.Font(asset_path("Press_Start_2P/PressStart2P-Regular.ttf"), 12 * SCALE_FACTOR)
scoreFont = pygame.font.Font(asset_path("digital_7/digital-7.ttf"), 250 * SCALE_FACTOR)

RED = (220, 0, 0)


# ==========================================================
# Clickable rects — derived from asset positions and scale
# ==========================================================

S  = SCALE_FACTOR
LS = LAST_SCALE_FACTOR
PW = profile_pictures[0].get_width()
PH = profile_pictures[0].get_height()
PROFILE_Y = 98 * S * LS

# Left screen: profile[0] on left, profile[1] on right
# Right screen: mirrored
profile_rects = [
    pygame.Rect(5 * S * LS,                                    PROFILE_Y, PW * LS, PH * LS),
    pygame.Rect((BASE_WIDTH - PW - 5 * S) * LS,               PROFILE_Y, PW * LS, PH * LS),
]
profile_rects1 = [
    pygame.Rect((BASE_WIDTH - PW - 5 * S) * LS + LEFT_WIDTH,  PROFILE_Y, PW * LS, PH * LS),
    pygame.Rect(5 * S * LS                  + LEFT_WIDTH,      PROFILE_Y, PW * LS, PH * LS),
]

SCW = score_coverR.get_width()
SCH = score_coverR.get_height()
SCORE_Y = 41 * S * LS

score_rects = [
    pygame.Rect(88 * S * LS,               SCORE_Y, SCW * LS, SCH * LS),
    pygame.Rect(BASE_WIDTH // 2 * LS,      SCORE_Y, SCW * LS, SCH * LS),
]
score_rects1 = [
    pygame.Rect(BASE_WIDTH // 2 * LS       + LEFT_WIDTH, SCORE_Y, SCW * LS, SCH * LS),
    pygame.Rect(88 * S * LS               + LEFT_WIDTH, SCORE_Y, SCW * LS, SCH * LS),
]

MCW = money_cover.get_width()
MCH = money_cover.get_height()

money_rects = [
    pygame.Rect(0,                                    0, MCW * LS // 2, MCH * LS),
    pygame.Rect((BASE_WIDTH - MCW // 2) * LS,         0, MCW * LS // 2, MCH * LS),
]
money_rects1 = [
    pygame.Rect((BASE_WIDTH - MCW // 2) * LS + LEFT_WIDTH, 0, MCW * LS // 2, MCH * LS),
    pygame.Rect(LEFT_WIDTH,                               0, MCW * LS // 2, MCH * LS),
]


# ==========================================================
# Render surfaces and cached state
# ==========================================================

render_surface  = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
render_surface0 = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))

score_surface1L = pygame.Surface((score_coverL.get_width(), score_coverL.get_height()))
score_surface1R = pygame.Surface((score_coverR.get_width(), score_coverR.get_height()))
score_surface2L = pygame.Surface((score_coverL.get_width(), score_coverL.get_height()))
score_surface2R = pygame.Surface((score_coverR.get_width(), score_coverR.get_height()))

last_score_1 = None
last_score_2 = None
last_money_1 = None
last_money_2 = None
background_surface1 = None
background_surface2 = None

last_windsock_frame_index = -1
score_change = False

# dirty flags: rebuild_base triggers a full background redraw;
# rebuild_dynamic redraws score/money on top of the existing background
rebuild_base    = True
rebuild_dynamic = False

# ==========================================================
# Wind particles
# ==========================================================

WIND_COUNT     = 200
WIND_SPEED_MIN = 300 * SCALE_FACTOR
WIND_SPEED_MAX = 500 * SCALE_FACTOR
WIND_WIDTH     = 10 * SCALE_FACTOR
WIND_HEIGHT    =  2 * SCALE_FACTOR
show_air       = False

class WindEffect:
    def __init__(self, mirror=False):
        self.mirror = mirror
        self.reset()

    def _owner(self):
        d = controller.air_owner
        return (2 if d == 1 else 1) if self.mirror else d

    def reset(self):
        self.y     = random.randint(0, BASE_HEIGHT)
        self.speed = random.uniform(WIND_SPEED_MIN, WIND_SPEED_MAX)
        self.x     = random.randint(-BASE_WIDTH, 0) if self._owner() == 1 else random.randint(BASE_WIDTH, BASE_WIDTH * 2)

    def update(self, dt):
        if self._owner() == 1:
            self.x += self.speed * dt
            if self.x > BASE_WIDTH:
                self.reset()
        else:
            self.x -= self.speed * dt
            if self.x < -WIND_WIDTH:
                self.reset()

    def draw(self, surface):
        pygame.draw.rect(surface, (200, 200, 200), (int(self.x), int(self.y), WIND_WIDTH, WIND_HEIGHT))

wind  = [WindEffect()     for _ in range(WIND_COUNT)]
wind0 = [WindEffect(True) for _ in range(WIND_COUNT)]

# ==========================================================
# Mouse hide
# ==========================================================

MOUSE_HIDE_DELAY = 5.0
last_mouse_move  = time.time()
mouse_visible    = True

clock   = pygame.time.Clock()
running = True


# ==========================================================
# Helper: handle a click on a pair of rect lists
# ==========================================================

def rects_clicked(pos, rects_left, rects_right):
    """Returns (index, screen) where screen is 'left' or 'right', or None."""
    for i, r in enumerate(rects_left):
        if r.collidepoint(pos):
            return i, "left"
    for i, r in enumerate(rects_right):
        if r.collidepoint(pos):
            return i, "right"
    return None


# ==========================================================
# Main loop
# ==========================================================

while running:
    start = time.perf_counter()
    dt = clock.tick(30) / 1000.0

    # ── Input ─────────────────────────────────────────────────────────────────
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

        elif event.type == pygame.MOUSEMOTION:
            last_mouse_move = time.time()
            if not mouse_visible:
                pygame.mouse.set_visible(True)
                mouse_visible = True

        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos

            # Profile picture — left click cycles forward, right click cycles back
            hit = rects_clicked(pos, profile_rects, profile_rects1)
            if hit:
                idx, _ = hit
                node_id = idx + 1
                direction = 1 if event.button == 1 else -1
                controller.cycle_profile(node_id, direction)
                rebuild_base = True

            # Score — left click +1, right click -1
            hit = rects_clicked(pos, score_rects, score_rects1)
            if hit:
                idx, _ = hit
                node_id = idx + 1
                if event.button == 1:
                    controller.score[node_id] += 1
                elif event.button == 3 and controller.score[node_id] > 0:
                    controller.score[node_id] -= 1
                rebuild_dynamic = True

            # Money — left click +10, right click -10
            hit = rects_clicked(pos, money_rects, money_rects1)
            if hit:
                idx, _ = hit
                node_id = idx + 1
                if event.button == 1:
                    controller.money[node_id] += 10
                elif event.button == 3:
                    controller.money[node_id] = max(0, controller.money[node_id] - 10)
                rebuild_dynamic = True

    # Mouse hide
    if mouse_visible and time.time() - last_mouse_move > MOUSE_HIDE_DELAY:
        pygame.mouse.set_visible(False)
        mouse_visible = False

    # ── Audio ─────────────────────────────────────────────────────────────────
    with controller._celebration_lock:
        pending_team = controller.pending_celebration
        controller.pending_celebration = None

    if pending_team is not None:
        audio.play_goal(pending_team)

    audio.update(dt)

    # ── Render: full background rebuild (profiles changed) ────────────────────
    if rebuild_base:
        if debug:
            print("[RENDER] Base rebuild")
        background_surface1 = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        background_surface2 = pygame.Surface((BASE_WIDTH, BASE_HEIGHT))
        background_surface1.blit(bane_img, (0, 0))
        background_surface2.blit(bane_img, (0, 0))

        p0 = profile_pictures[controller.profile_index[1]]
        p1 = profile_pictures[controller.profile_index[2]]

        background_surface1.blit(p0, (5 * S, 98 * S))
        background_surface1.blit(p1, (BASE_WIDTH - p1.get_width() - 5 * S, 98 * S))
        background_surface2.blit(p0, (BASE_WIDTH - p0.get_width() - 5 * S, 98 * S))
        background_surface2.blit(p1, (5 * S, 98 * S))

        rebuild_base    = False
        rebuild_dynamic = True  # always redraw dynamic content after a base rebuild

    # ── Render: dynamic content (score / money changed) ───────────────────────
    current_money_1 = controller.money[1]
    current_money_2 = controller.money[2]
    current_score_1 = controller.score[1]
    current_score_2 = controller.score[2]

    if current_money_1 != last_money_1 or rebuild_dynamic:
        background_surface1.blit(money_cover, (2 * S, 0))
        background_surface2.blit(money_cover, (BASE_WIDTH - money_cover.get_width() - 2 * S, 0))
        t = font.render(f"{current_money_1 // 20}", True, RED)
        background_surface1.blit(wind_img1, (20 * S + t.get_width(), -10 * S))
        background_surface2.blit(wind_img,  (BASE_WIDTH - 40 * S - wind_img.get_width() - t.get_width(), -10 * S))
        background_surface1.blit(t, (10 * S, 8 * S))
        background_surface2.blit(t, (BASE_WIDTH - 10 * S - t.get_width(), 8 * S))
        if current_money_1 % 20 != 0:
            half = fontSmall.render("½", True, RED)
            background_surface1.blit(half, (8 * S + t.get_width(), 24 * S))
            background_surface2.blit(half, (BASE_WIDTH - 13 * S, 24 * S))
        last_money_1 = current_money_1

    if current_money_2 != last_money_2 or rebuild_dynamic:
        background_surface2.blit(money_cover, (2 * S, 0))
        background_surface1.blit(money_cover, (BASE_WIDTH - money_cover.get_width() - 2 * S, 0))
        t = font.render(f"{current_money_2 // 20}", True, RED)
        background_surface2.blit(wind_img1, (20 * S + t.get_width(), -10 * S))
        background_surface1.blit(wind_img,  (BASE_WIDTH - 20 * S - wind_img.get_width() - t.get_width(), -10 * S))
        background_surface1.blit(t, (BASE_WIDTH - 10 * S - t.get_width(), 8 * S))
        background_surface2.blit(t, (10 * S, 8 * S))
        if current_money_2 % 20 != 0:
            half = fontSmall.render("½", True, RED)
            background_surface1.blit(half, (BASE_WIDTH - 13 * S, 24 * S))
            background_surface2.blit(half, (8 * S + t.get_width(), 24 * S))
        last_money_2 = current_money_2

    if current_score_1 != last_score_1 or rebuild_dynamic:
        score_surface1L.blit(score_coverL, (0, 0))
        score_surface1R.blit(score_coverR, (0, 0))
        t = scoreFont.render(str(current_score_1), True, RED)
        y = 94 * S - t.get_height() // 2
        score_surface1L.blit(t, (0, y))
        score_surface1R.blit(t, (152 * S - t.get_width(), y))
        background_surface1.blit(score_surface1L, (88 * S, 41 * S))
        background_surface2.blit(score_surface1R, (BASE_WIDTH // 2, 41 * S))
        score_change  = True
        last_score_1  = current_score_1

    if current_score_2 != last_score_2 or rebuild_dynamic:
        score_surface2L.blit(score_coverL, (0, 0))
        score_surface2R.blit(score_coverR, (0, 0))
        t = scoreFont.render(str(current_score_2), True, RED)
        y = 94 * S - t.get_height() // 2
        score_surface2R.blit(t, (152 * S - t.get_width(), y))
        score_surface2L.blit(t, (0, y))
        background_surface1.blit(score_surface2R, (BASE_WIDTH // 2, 41 * S))
        background_surface2.blit(score_surface2L, (88 * S, 41 * S))
        score_change  = True
        last_score_2  = current_score_2

    rebuild_dynamic = False

    # ── Render: windsock animation ────────────────────────────────────────────
    air_phase = controller.air_phase
    air_owner = controller.air_owner

    if air_phase != "IDLE":
        frame_index = (pygame.time.get_ticks() // 100) % len(windsock_frames)
        if frame_index != last_windsock_frame_index or score_change:
            show_air = True
            # Re-stamp score surfaces so windsock doesn't overwrite them
            background_surface1.blit(score_surface1L, (88 * S, 41 * S))
            background_surface2.blit(score_surface1R, (BASE_WIDTH // 2, 41 * S))
            background_surface1.blit(score_surface2R, (BASE_WIDTH // 2, 41 * S))
            background_surface2.blit(score_surface2L, (88 * S, 41 * S))

            if air_owner == 1:
                background_surface1.blit(windsock_frames[frame_index],  (178 * S, 168 * S))
                background_surface2.blit(windsock_frames1[frame_index], (178 * S, 168 * S))
            else:
                background_surface2.blit(windsock_frames[frame_index],  (178 * S, 168 * S))
                background_surface1.blit(windsock_frames1[frame_index], (178 * S, 168 * S))

            last_windsock_frame_index = frame_index
            score_change = False
    else:
        if last_windsock_frame_index != -1:
            rebuild_base = True  # clear windsock by rebuilding
            last_windsock_frame_index = -1
        show_air = False

    # ── Compose and flip ──────────────────────────────────────────────────────
    render_surface.blit(background_surface1, (0, 0))
    render_surface0.blit(background_surface2, (0, 0))

    if show_air:
        for p in wind:
            p.update(dt)
            p.draw(render_surface)
        for p in wind0:
            p.update(dt)
            p.draw(render_surface0)

    surface.blit(pygame.transform.scale_by(render_surface,  LAST_SCALE_FACTOR), (0, 0))
    surface.blit(pygame.transform.scale_by(render_surface0, LAST_SCALE_FACTOR), (LEFT_WIDTH, 0))
    window.flip()

    if debug:
        print(time.perf_counter() - start)

# ==========================================================
# Shutdown
# ==========================================================

audio.stop_all()
pygame.quit()