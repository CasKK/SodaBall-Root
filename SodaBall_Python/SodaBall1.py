import serial
import crcmod
import time
from collections import deque

crc8 = crcmod.predefined.mkCrcFun('crc-8')

ser = serial.Serial('COM5', 115200, timeout=0.1)

# =========================
# Incoming de-duplication
# =========================

seen = set()  # (arduino_id, seq)

# =========================
# Outgoing command state
# =========================

cmd_seq = 0
pending_cmds = {}      # seq -> (frame, last_send_time)
cmd_queue = deque()

RETRY_INTERVAL = 0.2   # seconds


# =========================
# Transport helpers
# =========================

def send_ack(arduino_id, seq):
    body = f"A,{arduino_id},{seq},OK"
    crc = crc8(body.encode())
    msg = f"${body}*{crc:02X}\n"
    ser.write(msg.encode())


# =========================
# Reliable command sender
# =========================

def send_command(arduino_id, domain, target, value):
    global cmd_seq

    body = f"C,{arduino_id},{cmd_seq},{domain},{target},{value}"
    frame = f"${body}*{crc8(body.encode()):02X}\n"

    pending_cmds[cmd_seq] = {
        "frame": frame,
        "time": time.time()
    }
    cmd_queue.append(cmd_seq)

    # SEND IMMEDIATELY
    ser.write(frame.encode())

    cmd_seq += 1



def process_command_queue():
    now = time.time()

    if not cmd_queue:
        return

    seq = cmd_queue[0]
    entry = pending_cmds.get(seq)

    if entry and now - entry["time"] > RETRY_INTERVAL:
        ser.write(entry["frame"].encode())
        entry["time"] = now



# =========================
# Main loop
# =========================

while True:

    # ---- Handle outgoing retries ----
    process_command_queue()

    # ---- Read incoming ----
    line = ser.readline().decode(errors='ignore').strip()
    if not line.startswith("$") or "*" not in line:
        continue

    body, crc_hex = line[1:].split("*", 1)

    try:
        if crc8(body.encode()) != int(crc_hex, 16):
            continue
    except ValueError:
        continue

    parts = body.split(",")
    msg_type = parts[0]
    arduino_id = int(parts[1])
    seq = int(parts[2])

    # =========================
    # ACK handling (for commands)
    # =========================

    if msg_type == "A":
        if seq in pending_cmds:
            del pending_cmds[seq]
            cmd_queue.popleft()
        continue

    # =========================
    # Incoming de-duplication
    # =========================

    key = (arduino_id, seq)
    if key in seen:
        send_ack(arduino_id, seq)
        continue

    seen.add(key)

    # =========================
    # Event handling
    # =========================

    if msg_type == "G":
        side = parts[3]
        print(f"GOAL from Arduino {arduino_id}: {side}")
        send_ack(arduino_id, seq)
    elif msg_type == "B":
        payload = parts[3]
        print(f"Button {arduino_id}: {payload}")
        send_ack(arduino_id, seq)
        send_command(arduino_id, "relay", "AIR", "ON" )
    elif msg_type == "S":
        sensor = parts[3]
        value = parts[4]
        print(f"Sensor {arduino_id}: {sensor} = {value}")
        send_ack(arduino_id, seq)
    else:
        # Unknown message → still ACK to stop retries
        send_ack(arduino_id, seq)
