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

polys = [0x07, 0x31, 0x1D, 0x9B]
inits = [0x00, 0xFF]

while True:
    buffer += ser.read(64)
    while len(buffer) >= FRAME_LEN:
        if buffer[0:2] == HEADER:
            frame = buffer[:FRAME_LEN]
            data = frame[:18]
            recv_crc = frame[18]
            print(f"Frame: {frame.hex()}")
            for poly in polys:
                for init in inits:
                    calc_crc = crc8_generic(data, polynomial=poly, initial_value=init)
                    match = calc_crc == recv_crc
                    print(f"  Poly: {hex(poly)}, Init: {hex(init)}, Calc CRC: {hex(calc_crc)}, Recv CRC: {hex(recv_crc)}, Match: {match}")
            print("-"*60)
            buffer = buffer[FRAME_LEN:]
        else:
            buffer = buffer[1:] 