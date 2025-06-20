import serial

def reflect_byte(b):
    return int('{:08b}'.format(b)[::-1], 2)

def crc8_mr72(buf):
    crc = 0xFF
    for b in buf:
        b = reflect_byte(b)
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x9B) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

ser = serial.Serial("/dev/ttyS0", 115200, timeout=1)

HEADER = bytes([0x54, 0x48])
FRAME_LEN = 19

buffer = b''

while True:
    buffer += ser.read(64)
    while len(buffer) >= FRAME_LEN:
        if buffer[0:2] == HEADER:
            frame = buffer[:FRAME_LEN]
            data = frame[:17]
            recv_crc = frame[17]
            calc_crc = crc8_mr72(data)
            if calc_crc == recv_crc:
                print(frame)
            buffer = buffer[FRAME_LEN:]
        else:
            buffer = buffer[1:] 