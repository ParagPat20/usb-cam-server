import serial
import time
from pymavlink import mavutil

# UART and FC settings
MR72_PORT, MR72_BAUD = '/dev/ttyS0', 115200
FC_PORT, FC_BAUD = '/dev/ttyACM1', 115200
FAKE_DISTANCE, MIN_DISTANCE, MAX_DISTANCE = 3000, 30, 3000
SECTOR_ORIENTATION = {1:1,2:0,3:7,4:6,5:5,6:4,7:3,8:2}

def parse_mr72(pkt: bytes):
    print(f"Parsing packet: {pkt.hex()}")
    if len(pkt) != 19 or not pkt.startswith(b'TH'):
        print(f" → Invalid packet length {len(pkt)} or header mismatch")
        return None
    d2 = int.from_bytes(pkt[2:4], 'big')
    d3 = int.from_bytes(pkt[4:6], 'big')
    d8 = int.from_bytes(pkt[16:18], 'big')
    data = {i: FAKE_DISTANCE for i in range(1,9)}
    data[1] = d8 if d8 != 0xFFFF else FAKE_DISTANCE
    data[2] = d2 if d2 != 0xFFFF else FAKE_DISTANCE
    data[3] = d3 if d3 != 0xFFFF else FAKE_DISTANCE
    print(f" → Raw distances - S1: {data[1]}, S2: {data[2]}, S3: {data[3]}")
    return data

def send_distance(master, d_cm, orient):
    print(f"Sending distance: {d_cm}cm at orientation {orient}")
    master.mav.distance_sensor_send(
        time_boot_ms=0,
        min_distance=MIN_DISTANCE,
        max_distance=MAX_DISTANCE,
        current_distance=d_cm,
        type=0, id=0, orientation=orient, covariance=0
    )

def main():
    rs = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)
    mav = mavutil.mavlink_connection(FC_PORT, baud=FC_BAUD)
    mav.wait_heartbeat()
    print("MAVLink heartbeat received — ready to start parsing")

    buffer = bytearray()
    got_TH = False

    while True:
        b = rs.read(1)
        if not b:
            continue
        buffer += b

        if not got_TH:
            if buffer.endswith(b'TH'):
                got_TH = True
                buffer = bytearray(b'TH')
                print("→ Found start header 'TH', entering record mode")
            else:
                if len(buffer) > 2:
                    removed = buffer.pop(0)
                    print(f"Invalid header byte removed: {removed:#04x}")
        else:
            if buffer.endswith(b'TH'):
                # we got a full packet
                pkt_body = buffer[:-2]
                buffer = bytearray(b'TH')
                print("→ End header 'TH' found; packet boundary")
                got_TH = True
                if pkt_body:
                    pkt = b'TH' + pkt_body
                    sd = parse_mr72(pkt)
                    if sd:
                        for sid, dist in sd.items():
                            send_distance(mav, dist, SECTOR_ORIENTATION[sid])
                        print("All distance sensor messages sent\n")

if __name__ == "__main__":
    main()
