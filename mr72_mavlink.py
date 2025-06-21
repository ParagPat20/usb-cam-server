import serial
import time
from pymavlink import mavutil

# UART settings
MR72_PORT, MR72_BAUD = '/dev/ttyS0', 115200
FC_PORT, FC_BAUD = '/dev/ttyACM3', 115200

# Distance sensor constants (cm)
FAKE_DISTANCE = 1000
MIN_DISTANCE = 30
MAX_DISTANCE = 3000

# Map to MAVLink orientations (0–7)
SECTOR_ORIENTATION = {
    2: 0,  # front-center
    1: 1,  # front-left
    8: 2,  # left
    7: 3,  # back-left
    6: 4,  # back
    5: 5,  # back-right
    4: 6,  # right
    3: 7   # front-right
}

def parse_packet(pkt: bytes):
    d2 = int.from_bytes(pkt[2:4], 'big')
    d3 = int.from_bytes(pkt[4:6], 'big')
    d8 = int.from_bytes(pkt[16:18], 'big')

    def mm_to_cm(v):
        return v // 10 if v != 0xFFFF else FAKE_DISTANCE

    distances = {
        sid: (
            mm_to_cm(d8) if sid == 1 else
            mm_to_cm(d2) if sid == 2 else
            mm_to_cm(d3) if sid == 3 else
            FAKE_DISTANCE
        ) for sid in range(1, 9)
    }

    # Print full converted data
    print("Converted sector distances (cm):")
    for sid, dist in distances.items():
        print(f"  Sector {sid}: {dist} cm")

    return distances
def send_heartbeat(master):
    master.mav.heartbeat_send(
        type=6, autopilot=8, base_mode=0,
        custom_mode=0, system_status=4
    )

def send_distances(master, distances):
    for sid, d in distances.items():
        orient = SECTOR_ORIENTATION[sid]
        print(f"  → Sending {d/100} m at orientation {orient}")
        master.mav.distance_sensor_send(
            time_boot_ms=0,
            min_distance=MIN_DISTANCE,
            max_distance=MAX_DISTANCE,
            current_distance=d,
            type=0, id=0,
            orientation=orient,
            covariance=0
        )
    print("All 8 sectors sent.\n")

def main():
    rs = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)
    mav = mavutil.mavlink_connection(
        FC_PORT,
        baud=FC_BAUD,
        source_system=1,
        source_component=158  # Companion component
    )
    mav.wait_heartbeat()
    print("MAVLink heartbeat established (system=1, comp=158)")

    last_hb = time.time()
    buf = bytearray()

    while True:
        if time.time() - last_hb >= 1.0:
            send_heartbeat(mav)
            last_hb = time.time()

        # Sync: read until we get "TH" header
        if len(buf) < 2:
            buf += rs.read(2 - len(buf))
            continue
        if buf[:2] != b'TH':
            buf.pop(0)
            continue

        rest = rs.read(17)
        if len(rest) != 17:
            print(f"Incomplete packet: only {len(rest)+2} bytes")
            buf.clear()
            continue

        pkt = b'TH' + rest
        buf.clear()
        sd = parse_packet(pkt)
        if sd:
            send_distances(mav, sd)
            time.sleep(0.1)  # throttle to ~10 Hz

if __name__ == '__main__':
    main()
