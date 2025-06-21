import serial
import time
from pymavlink import mavutil

MR72_PORT, MR72_BAUD = '/dev/ttyS0', 115200
FC_PORT, FC_BAUD = '/dev/ttyACM3', 115200

FAKE_DISTANCE = 1000  # cm
MIN_DISTANCE = 30
MAX_DISTANCE = 3000

SECTOR_ORIENTATION = {
    2: 0,  # front-center
    1: 1,  # front-left
    8: 2,  # left
    7: 3,  # back-left
    6: 4,  # back-center
    5: 5,  # back-right
    4: 6,  # right
    3: 7   # front-right
}

SEND_INTERVAL = 0.1  # 20 Hz send rate

def parse_packet(pkt):
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
    return distances

def send_heartbeat(mav):
    mav.mav.heartbeat_send(type=6, autopilot=8, base_mode=0,
                            custom_mode=0, system_status=4)

def send_distances(mav, dist):
    for sid, d in dist.items():
        mav.mav.distance_sensor_send(
            time_boot_ms=0,
            min_distance=MIN_DISTANCE,
            max_distance=MAX_DISTANCE,
            current_distance=d,
            type=0, id=0,
            orientation=SECTOR_ORIENTATION[sid],
            covariance=0
        )

def main():
    rs = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)
    rs.reset_input_buffer()
    mav = mavutil.mavlink_connection(
        FC_PORT, baud=FC_BAUD, source_system=1, source_component=158)
    mav.wait_heartbeat()

    last_hb = time.time()
    next_send = time.time()

    buf = bytearray()
    while True:
        if time.time() - last_hb > 1.0:
            send_heartbeat(mav)
            last_hb = time.time()

        buf += rs.read(rs.in_waiting or 1)
        if len(buf) < 19:
            continue
        offset = buf.find(b'TH')
        if offset < 0:
            buf.clear()
            continue
        if len(buf) - offset < 19:
            continue
        pkt = buf[offset:offset+19]
        buf = buf[offset+19:]
        distances = parse_packet(pkt)

        now = time.time()
        if now >= next_send:
            send_distances(mav, distances)
            next_send += SEND_INTERVAL
            if now > next_send:
                next_send = now

if __name__ == '__main__':
    main()
