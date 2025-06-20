import serial

ser = serial.Serial("/dev/ttyS0", 115200, timeout=1)

HEADER = bytes([0x54, 0x48])
FRAME_LEN = 19

def crc8_generic(buf, polynomial=0x07, initial_value=0x00):
    crc = initial_value
    for b in buf:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ polynomial) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

buffer = b''

while True:
    buffer += ser.read(64)
    while len(buffer) >= FRAME_LEN:
        if buffer[0:2] == HEADER:
            frame = buffer[:FRAME_LEN]
            # CRC8 check: first 18 bytes, compare to 19th
            if crc8_generic(frame[:18], polynomial=0x07, initial_value=0x00) == frame[18]:
                print(frame)
            buffer = buffer[FRAME_LEN:]
        else:
            buffer = buffer[1:] 