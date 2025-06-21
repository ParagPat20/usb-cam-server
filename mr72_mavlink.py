import serial
import time
from pymavlink import mavutil

# MR72 UART config
MR72_PORT = '/dev/ttyS0'
MR72_BAUD = 115200

# FC MAVLink config
FC_PORT = '/dev/ttyACM3'
FC_BAUD = 115200

# Constants
FAKE_DISTANCE = 3000  # cm
MIN_DISTANCE = 30     # cm
MAX_DISTANCE = 3000   # cm

# MR72 gives 3 sectors: front-left (1), front-center (2), front-right (3)
# Orientation values per ArduPilot docs: 0–7 (each 45° clockwise from front)
SECTOR_ORIENTATION = {
    1: 1,  # Yaw 45 (Front-Left)
    2: 0,  # Forward
    3: 7,  # Yaw 315 (Front-Right)
    4: 6,  # Yaw 270 (Right)
    5: 5,  # Yaw 225 (Back-Right)
    6: 4,  # Back
    7: 3,  # Yaw 135 (Back-Left)
    8: 2   # Yaw 90 (Left)
}

def parse_mr72(packet: bytes):
    if len(packet) < 19 or packet[:2] != b'TH':
        return None
    try:
        d2 = int.from_bytes(packet[2:4], 'big')   # Sector 2: front-center
        d3 = int.from_bytes(packet[4:6], 'big')   # Sector 3: front-right
        d8 = int.from_bytes(packet[16:18], 'big') # Sector 1: front-left
        return {
            1: d8 if d8 != 0xFFFF else FAKE_DISTANCE,
            2: d2 if d2 != 0xFFFF else FAKE_DISTANCE,
            3: d3 if d3 != 0xFFFF else FAKE_DISTANCE,
            4: FAKE_DISTANCE,
            5: FAKE_DISTANCE,
            6: FAKE_DISTANCE,
            7: FAKE_DISTANCE,
            8: FAKE_DISTANCE,
        }
    except:
        return None

def send_distance(master, distance_cm, orientation):
    master.mav.distance_sensor_send(
        time_boot_ms=0,
        min_distance=MIN_DISTANCE,
        max_distance=MAX_DISTANCE,
        current_distance=distance_cm,
        type=0,
        id=0,
        orientation=orientation,
        covariance=0
    )

def main():
    radar_serial = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)
    mav = mavutil.mavlink_connection(FC_PORT, baud=FC_BAUD)
    mav.wait_heartbeat()
    print("MAVLink heartbeat received")

    buffer = bytearray()

    while True:
        byte = radar_serial.read(1)
        if not byte:
            continue
        buffer += byte

        if len(buffer) >= 2 and buffer[:2] != b'TH':
            buffer.pop(0)
            continue

        if len(buffer) >= 19:
            packet = bytes(buffer[:19])
            buffer = buffer[19:]
            data = parse_mr72(packet)

            if data:
                for sector_id, distance in data.items():
                    orientation = SECTOR_ORIENTATION[sector_id]
                    send_distance(mav, distance, orientation)

        time.sleep(0.05)  # ~20 Hz sending rate

if __name__ == "__main__":
    main()
