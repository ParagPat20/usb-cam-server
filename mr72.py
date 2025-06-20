import serial


def parse_sectors(frame):
    # frame is 19 bytes, already validated
    def parse_distance(msb, lsb):
        val = (msb << 8) | lsb
        return None if val == 0xFFFF else val
    sector2 = parse_distance(frame[2], frame[3])
    sector3 = parse_distance(frame[4], frame[5])
    sector1 = parse_distance(frame[16], frame[17])
    return sector1, sector2, sector3


# Setup serial (adjust port and baudrate if needed)
ser = serial.Serial("/dev/ttyS0", 115200, timeout=1)
buffer = bytearray()

while True:
    data = ser.read(64)
    buffer.extend(data)

    while len(buffer) >= 19:
        frame = buffer[:19]
        sector1, sector2, sector3 = parse_sectors(frame)
        print(f"Sector 1: {sector1} mm, Sector 2: {sector2} mm, Sector 3: {sector3} mm")
        buffer = buffer[19:]
