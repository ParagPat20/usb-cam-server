import serial
import time
from pymavlink import mavutil

# MR72 config
MR72_PORT = '/dev/ttyS0'  # Radar UART
MR72_BAUD = 115200

# Flight Controller config
FC_PORT = '/dev/ttyACM3'  # SLCAN port or MAVLink UART
FC_BAUD = 115200

# Fake obstacle distance for sectors that MR72 does not support (in cm)
FAKE_DISTANCE = 3000

# Sensor details
SENSOR_ID = 1  # Arbitrary, must be unique if multiple

# Sector mappings (sector_id: orientation in degrees)
# Mapping of sector_id to MAV_SENSOR_ORIENTATION enum values
SECTOR_ANGLES = {
    1: 8,   # MAV_SENSOR_ROTATION_YAW_45 (Front-Left)
    2: 0,   # MAV_SENSOR_ROTATION_NONE (Forward)
    3: 7,   # MAV_SENSOR_ROTATION_YAW_135 (Front-Right)
    4: 4,   # MAV_SENSOR_ROTATION_YAW_180 (Back)
    5: 5,   # MAV_SENSOR_ROTATION_YAW_225
    6: 6,   # MAV_SENSOR_ROTATION_YAW_270
    7: 3,   # MAV_SENSOR_ROTATION_YAW_315
    8: 1    # MAV_SENSOR_ROTATION_YAW_90 (Right)
}


def parse_mr72_packet(packet: bytes):
    if len(packet) < 19 or not (packet[0] == ord('T') and packet[1] == ord('H')):
        return None

    try:
        # Extract sector data (2 bytes each, big endian)
        d2 = int.from_bytes(packet[2:4], 'big')  # Sector 2 (Front-Center)
        d3 = int.from_bytes(packet[4:6], 'big')  # Sector 3 (Front-Right)
        d8 = int.from_bytes(packet[16:18], 'big')  # Sector 1 (Front-Left)

        # Replace 0xFFFF with 3000cm
        sector_data = {
            1: d8 if d8 != 0xFFFF else FAKE_DISTANCE,
            2: d2 if d2 != 0xFFFF else FAKE_DISTANCE,
            3: d3 if d3 != 0xFFFF else FAKE_DISTANCE,
        }

        # Fake values for sectors not supported
        for sid in [4, 5, 6, 7, 8]:
            sector_data[sid] = FAKE_DISTANCE

        return sector_data
    except Exception as e:
        print(f"Parse error: {e}")
        return None


def send_distance_sensor(master, current_time_ms, distance_cm, orientation):
    master.mav.distance_sensor_send(
        time_boot_ms=current_time_ms,
        min_distance=30,
        max_distance=3000,
        current_distance=distance_cm,
        type=0,                    # MAV_DISTANCE_SENSOR_LASER
        id=SENSOR_ID,             # Must be in range 0–255
        orientation=orientation,  # Must be in range 0–255 (MAV enum)
        covariance=255,           # Unknown
        horizontal_fov=0,
        vertical_fov=0,
        quaternion=[0, 0, 0, 0],
        signal_quality=255
    )


def main():
    # Open radar serial
    radar_serial = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)

    # Connect MAVLink
    mav = mavutil.mavlink_connection(FC_PORT, baud=FC_BAUD)
    mav.wait_heartbeat()
    print("MAVLink heartbeat received")

    buffer = bytearray()

    while True:
        byte = radar_serial.read(1)
        if not byte:
            continue

        buffer += byte

        # Sync to 'T''H' start
        if len(buffer) >= 2 and buffer[:2] != b'TH':
            buffer = buffer[1:]
            continue

        if len(buffer) >= 19:
            packet = bytes(buffer[:19])
            buffer = buffer[19:]  # Remove processed packet

            sector_data = parse_mr72_packet(packet)
            if sector_data:
                timestamp_ms = int((time.time() - mav.start_time) * 1000) % 4294967295
                for sector_id, orientation in SECTOR_ANGLES.items():
                    send_distance_sensor(
                        master=mav,
                        current_time_us=timestamp_ms,
                        distance_cm=sector_data[sector_id],
                        orientation_deg=orientation
                    )



if __name__ == '__main__':
    main()
