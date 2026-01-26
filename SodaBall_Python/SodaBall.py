import serial
import crcmod

crc8 = crcmod.predefined.mkCrcFun('crc-8')

ser = serial.Serial('COM5', 115200, timeout=0.1)
seen = set()  # (id, seq) pairs

def send_ack(arduino_id, seq):
    body = f"A,{arduino_id},{seq},OK"
    crc = crc8(body.encode())
    msg = f"${body}*{crc:02X}\n"
    ser.write(msg.encode())

while True:
    line = ser.readline().decode(errors='ignore').strip()
    if not line.startswith("$") or "*" not in line:
        continue

    body, crc_hex = line[1:].split("*")
    if crc8(body.encode()) != int(crc_hex, 16):
        continue

    parts = body.split(",")
    msg_type, arduino_id, seq = parts[0], int(parts[1]), int(parts[2])

    if (arduino_id, seq) in seen:
        send_ack(arduino_id, seq)
        continue

    seen.add((arduino_id, seq))

    if msg_type == "G":
        side = parts[3]
        print(f"GOAL from Arduino {arduino_id}: {side}")
        send_ack(arduino_id, seq)

    if msg_type == "B":
        payload = parts[3]
        print(f"Button {arduino_id}: {payload}")
        send_ack(arduino_id, seq)
