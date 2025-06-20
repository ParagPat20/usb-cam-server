import serial

def reflect_byte(b):
    return int('{:08b}'.format(b)[::-1], 2)

def crc8_variant(buf, polynomial=0x07, initial_value=0x00, reflect_in=False, reflect_out=False, final_xor=0x00):
    crc = initial_value
    for b in buf:
        if reflect_in:
            b = reflect_byte(b)
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ polynomial) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    if reflect_out:
        crc = reflect_byte(crc)
    return crc ^ final_xor

ser = serial.Serial("/dev/ttyS0", 115200, timeout=1)

HEADER = bytes([0x54, 0x48])
FRAME_LEN = 19

polys = [0x07, 0x31, 0x1D, 0x9B]
inits = [0x00, 0xFF]
reflects = [False, True]
final_xors = [0x00, 0xFF]
data_lens = [17, 18, 19]

buffer = b''

while True:
    buffer += ser.read(64)
    while len(buffer) >= FRAME_LEN:
        if buffer[0:2] == HEADER:
            frame = buffer[:FRAME_LEN]
            recv_crc = frame[18]
            print(f"Frame: {frame.hex()}")
            for data_len in data_lens:
                data = frame[:data_len]
                for poly in polys:
                    for init in inits:
                        for ref_in in reflects:
                            for ref_out in reflects:
                                for fxor in final_xors:
                                    calc_crc = crc8_variant(data, polynomial=poly, initial_value=init, reflect_in=ref_in, reflect_out=ref_out, final_xor=fxor)
                                    match = calc_crc == recv_crc
                                    print(f"  Len:{data_len} Poly:{hex(poly)} Init:{hex(init)} RefIn:{ref_in} RefOut:{ref_out} FXor:{hex(fxor)} Calc:{hex(calc_crc)} Recv:{hex(recv_crc)} Match:{match}")
            print("-"*60)
            buffer = buffer[FRAME_LEN:]
        else:
            buffer = buffer[1:] 