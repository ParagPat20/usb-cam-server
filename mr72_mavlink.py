import serial
import time
from pymavlink import mavutil

# UART settings
MR72_PORT, MR72_BAUD = '/dev/ttyS0', 115200
FC_PORT, FC_BAUD = '/dev/ttyACM3', 115200

# Distance constants (cm)
FAKE_DISTANCE = 1000  # used when sector not measured
MIN_DISTANCE = 30
MAX_DISTANCE = 3000

# Map sectors (1–8) to MAVLink orientations (0–7)
SECTOR_ORIENTATION = {
    2: 0,  # front-center (0°)
    1: 1,  # front-left   (45°)
    8: 2,  # left         (90°)
    7: 3,  # back-left    (135°)
    6: 4,  # back         (180°)
    5: 5,  # back-right   (225°)
    4: 6,  # right        (270°)
    3: 7   # front-right  (315°)
}

def parse_packet(pkt: bytes):
    """Extract and convert sector distances from a 19-byte MR72 packet."""
    d2 = int.from_bytes(pkt[2:4], 'big')   # front-center (mm)
    d3 = int.from_bytes(pkt[4:6], 'big')   # front-right  (mm)
    d8 = int.from_bytes(pkt[16:18], 'big') # front-left   (mm)

    def mm_to_cm(val_mm):
        return val_mm // 10 if val_mm != 0xFFFF else FAKE_DISTANCE

    # Build full 8-sector dictionary with converted values
    distances = {
        sid: (
            mm_to_cm(d8) if sid == 1 else
            mm_to_cm(d2) if sid == 2 else
            mm_to_cm(d3) if sid == 3 else
            FAKE_DISTANCE
        )
        for sid in range(1, 9)
    }

    print("Converted sector distances (cm):")
    for sid, cm in distances.items():
        print(f"  Sector {sid}: {cm} cm")

    return distances

def send_heartbeat(mav):
    mav.mav.heartbeat_send(
        type=6, autopilot=8, base_mode=0,
        custom_mode=0, system_status=4
    )

def send_distances(mav, distances):
    """Transmit a DISTANCE_SENSOR message for each of the 8 sectors."""
    for sid, d in distances.items():
        orient = SECTOR_ORIENTATION[sid]
        print(f"  → Sending {d} cm at orientation {orient}")
        mav.mav.distance_sensor_send(
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
    rs.reset_input_buffer()  # Clear any stale data on startup
    mav = mavutil.mavlink_connection(
        FC_PORT, baud=FC_BAUD,
        source_system=1,
        source_component=158  # Companion component
    )
    mav.wait_heartbeat()
    print("MAVLink heartbeat established (sys=1, comp=158)")

    last_hb = time.time()
    buf = bytearray()

    while True:
        # Maintain 1 Hz heartbeats
        if time.time() - last_hb >= 1.0:
            send_heartbeat(mav)
            last_hb = time.time()

        # Synchronize on 'TH' header
        if len(buf) < 2:
            buf += rs.read(2 - len(buf))
            continue
        if buf[:2] != b'TH':
            buf.pop(0)
            continue

        # Read exact packet length (17 bytes after header)
        rest = rs.read(17)
        buf.clear()

        if len(rest) != 17:
            print("Incomplete packet, discarding.")
            continue

        pkt = b'TH' + rest
        distances = parse_packet(pkt)
        send_distances(mav, distances)
        # No long sleep—immediately loop around to stay in sync

if __name__ == '__main__':
    main()
