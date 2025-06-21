import serial
import time
from pymavlink import mavutil

# UART settings
MR72_PORT, MR72_BAUD = '/dev/ttyS0', 115200
FC_PORT, FC_BAUD = '/dev/ttyACM3', 115200

# Distance sensor constants (in cm)
FAKE_DISTANCE = 1000  # yes, this is 10 m
MIN_DISTANCE = 30
MAX_DISTANCE = 3000

# Map sensor sectors to MAVLink orientations 0–7
SECTOR_ORIENTATION = {
    2: 0,  # front-center → 0°
    1: 1,  # front-left   → 45°
    8: 2,  # left         → 90°
    7: 3,  # back-left    → 135°
    6: 4,  # back-center  → 180°
    5: 5,  # back-right   → 225°
    4: 6,  # right        → 270°
    3: 7   # front-right  → 315°
}

def parse_packet(pkt: bytes):
    print(f"Got full packet ({len(pkt)} bytes): {pkt.hex()}")
    if len(pkt) != 19 or not pkt.startswith(b'TH'):
        print(" → Discarding invalid packet")
        return None

    # MR72 gives mm, convert to cm
    d2 = int.from_bytes(pkt[2:4], 'big')   # center
    d3 = int.from_bytes(pkt[4:6], 'big')   # front-right
    d8 = int.from_bytes(pkt[16:18], 'big') # front-left

    def mm_to_cm(v):
        return v // 10 if v != 0xFFFF else FAKE_DISTANCE

    distances = {
        sid: (
            mm_to_cm(d8) if sid == 1 else
            mm_to_cm(d2) if sid == 2 else
            mm_to_cm(d3) if sid == 3 else
            FAKE_DISTANCE
        )
        for sid in range(1, 9)
    }

    print(f" → Parsed distances: S1={distances[1]}cm (45°L), "
          f"S2={distances[2]}cm (0°), S3={distances[3]}cm (315°R)")
    return distances

def send_heartbeat(master):
    master.mav.heartbeat_send(
        type=6, autopilot=8, base_mode=0,
        custom_mode=0, system_status=4
    )

def send_distances(master, distances):
    for sid, d in distances.items():
        orient = SECTOR_ORIENTATION[sid]
        print(f"  → Sending {d} cm at orientation {orient}")
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
