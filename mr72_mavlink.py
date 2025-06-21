import serial
import time
from pymavlink import mavutil

# UART settings
MR72_PORT, MR72_BAUD = '/dev/ttyS0', 115200
FC_PORT, FC_BAUD = '/dev/ttyACM1', 115200

# Distance sensor constants
FAKE_DISTANCE, MIN_DISTANCE, MAX_DISTANCE = 3000, 30, 3000
SECTOR_ORIENTATION = {1:1, 2:0, 3:7, 4:6, 5:5, 6:4, 7:3, 8:2}

def parse_packet(pkt: bytes):
    print(f"Got full packet ({len(pkt)} bytes): {pkt.hex()}")
    if len(pkt) != 19 or not pkt.startswith(b'TH'):
        print(" → Discarding: invalid size or header")
        return None
    d2 = int.from_bytes(pkt[2:4], 'big')
    d3 = int.from_bytes(pkt[4:6], 'big')
    d8 = int.from_bytes(pkt[16:18], 'big')
    data = {i: FAKE_DISTANCE for i in range(1,9)}
    data[1] = d8 if d8 != 0xFFFF else FAKE_DISTANCE
    data[2] = d2 if d2 != 0xFFFF else FAKE_DISTANCE
    data[3] = d3 if d3 != 0xFFFF else FAKE_DISTANCE
    print(f" → Parsed distances: S1={data[1]}, S2={data[2]}, S3={data[3]}")
    return data

def send_heartbeat(master):
    master.mav.heartbeat_send(
        type=6, autopilot=8, base_mode=0, custom_mode=0, system_status=4
    )

def send_distances(master, distances):
    for sid, d in distances.items():
        orient = SECTOR_ORIENTATION[sid]
        print(f"Sending distance: {d}cm at orientation {orient}")
        master.mav.distance_sensor_send(
            time_boot_ms=0,
            min_distance=MIN_DISTANCE,
            max_distance=MAX_DISTANCE,
            current_distance=d,
            type=0, id=0, orientation=orient, covariance=0
        )

def main():
    rs = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)
    mav = mavutil.mavlink_connection(FC_PORT, baud=FC_BAUD)
    mav.wait_heartbeat()
    print("MAVLink heartbeat received; starting radar parsing.")

    last_heartbeat = time.time()
    buf = bytearray()

    while True:
        # send heartbeat 1 Hz
        if time.time() - last_heartbeat >= 1:
            send_heartbeat(mav)
            last_heartbeat = time.time()

        # sync to TH
        if len(buf) < 2:
            buf += rs.read(2 - len(buf))
            continue
        if buf[:2] != b'TH':
            buf.pop(0)
            continue

        # read rest of packet
        rest = rs.read(17)
        if len(rest) != 17:
            print(f"Incomplete packet: only {len(rest)+2} bytes.")
            buf = bytearray()  # reset sync
            continue

        pkt = b'TH' + rest
        buf = bytearray()  # reset for next packet

        sd = parse_packet(pkt)
        if sd:
            send_distances(mav, sd)
            print("All sensor messages sent.\n")

if __name__ == '__main__':
    main()
