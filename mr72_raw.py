import serial

ser = serial.Serial("/dev/ttyS0", 115200, timeout=1)

HEADER = bytes([0x54, 0x48])
FRAME_LEN = 19

buffer = b''

while True:
    buffer += ser.read(64)  # Read a chunk for efficiency
    while len(buffer) >= FRAME_LEN:
        if buffer[0:2] == HEADER:
            frame = buffer[:FRAME_LEN]
            print(frame)
            buffer = buffer[FRAME_LEN:]
        else:
            # Discard first byte and realign
            buffer = buffer[1:] 