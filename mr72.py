import serial


def parse_sector(frame, msb_index, lsb_index):
    if len(frame) != 19:
        return None
    # Check header
    if frame[0] != 0x54 or frame[1] != 0x48:
        return None
    msb, lsb = frame[msb_index], frame[lsb_index]
    val = (msb << 8) | lsb
    return val

# Setup serial (adjust port and baudrate if needed)
ser = serial.Serial("/dev/ttyS0", 115200, timeout=1)

while True:
    frame = ser.read(19)
    sector3 = parse_sector(frame, 4, 5)
    print(f"Sector 3: {sector3} mm")
