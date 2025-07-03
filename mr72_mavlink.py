import serial, time
from pymavlink import mavutil
from filterpy.kalman import KalmanFilter
import numpy as np

# Serial & MAVLink settings...
MR72_PORT, MR72_BAUD = '/dev/ttyS0', 115200
FC_PORT, FC_BAUD = '/dev/serial/by-id/usb-ArduPilot_Pixhawk6X_36004E001351333031333637-if00', 115200
FAKE_DISTANCE = 3000
MIN_DISTANCE, MAX_DISTANCE = 30, 3000
SECTOR_ORIENTATION = {2:0,1:1,8:2,7:3,6:4,5:5,4:6,3:7}
SEND_INTERVAL = 0.1  # 10 Hz

# 📈 Kalman setup for each sector
filters = {}
for sid in range(1, 9):
    kf = KalmanFilter(dim_x=1, dim_z=1)
    kf.x = np.array([[FAKE_DISTANCE]])
    kf.P *= 1000
    kf.F = np.array([[1]])
    kf.H = np.array([[1]])
    kf.R = np.array([[100]])   # measurement noise
    kf.Q = np.array([[0.1]])   # process noise
    filters[sid] = kf

def parse_packet(pkt):
    d2 = int.from_bytes(pkt[2:4], 'big')
    d3 = int.from_bytes(pkt[4:6], 'big')
    d8 = int.from_bytes(pkt[16:18], 'big')
    def mm_to_cm(v): return v//10 if v != 0xFFFF else FAKE_DISTANCE
    raw = {sid: (
        mm_to_cm(d8) if sid == 1 else
        mm_to_cm(d2) if sid == 2 else
        mm_to_cm(d3) if sid == 3 else
        FAKE_DISTANCE
    ) for sid in range(1,9)}
    print("[RAW]    " + ", ".join(f"S{sid}={raw[sid]}" for sid in range(1,9)))
    return raw

def smooth(raw):
    smoothed = {}
    for sid, meas in raw.items():
        kf = filters[sid]
        kf.predict()
        kf.update(np.array([[meas]]))
        smoothed[sid] = float(kf.x)
    print("[KALMAN] " + ", ".join(f"S{sid}={smoothed[sid]:.1f}" for sid in sorted(smoothed)))
    return smoothed

def send_distances(mav, dist):
    t = time.time()
    print(f"[SEND @ {t:.3f}]" + ", ".join(f"S{sid}:{int(dist[sid])}cm" for sid in sorted(dist)))
    for sid, d in dist.items():
        mav.mav.distance_sensor_send(
            time_boot_ms=0, min_distance=MIN_DISTANCE,
            max_distance=MAX_DISTANCE, current_distance=int(d),
            type=0, id=0,
            orientation=SECTOR_ORIENTATION[sid],
            covariance=0
        )

def main():
    rs = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)
    rs.reset_input_buffer()
    mav = mavutil.mavlink_connection(FC_PORT, baud=FC_BAUD,
                                     source_system=1, source_component=158)
    mav.wait_heartbeat()
    print("[DEBUG] Heartbeat OK. Starting...")

    last_hb = time.time()
    next_send = time.time()

    buf = bytearray()
    while True:
        if time.time() - last_hb >= 1.0:
            mav.mav.heartbeat_send(type=6, autopilot=8,
                                   base_mode=0, custom_mode=0, system_status=4)
            last_hb = time.time()

        buf += rs.read(rs.in_waiting or 1)
        offset = buf.find(b'TH')
        if offset < 0:
            if len(buf) > 200: buf.clear()
            continue
        if len(buf) - offset < 19: continue

        pkt = buf[offset:offset+19]
        buf = buf[offset+19:]
        raw = parse_packet(pkt)
        filtered = smooth(raw)

        if time.time() >= next_send:
            send_distances(mav, filtered)
            next_send += SEND_INTERVAL
            if time.time() > next_send:
                next_send = time.time()

if __name__ == "__main__":
    main()
