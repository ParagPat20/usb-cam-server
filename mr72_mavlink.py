import serial
import time
from pymavlink import mavutil

MR72_PORT, MR72_BAUD = '/dev/ttyS0', 115200
FC_PORT, FC_BAUD = '/dev/ttyACM3', 115200

FAKE_DISTANCE = 1000  # cm for unmeasured sectors
MIN_DISTANCE = 30
MAX_DISTANCE = 3000

SECTOR_ORIENTATION = {2:0,1:1,8:2,7:3,6:4,5:5,4:6,3:7}
SEND_INTERVAL = 0.2  # 5 Hz

# Setup EMA smoothing (alpha close to 1: smoother)
EMA_ALPHA = 0.3
ema = {sid: FAKE_DISTANCE for sid in range(1,9)}

def parse_packet(pkt):
    d2 = int.from_bytes(pkt[2:4], 'big')
    d3 = int.from_bytes(pkt[4:6], 'big')
    d8 = int.from_bytes(pkt[16:18], 'big')
    def mm_to_cm(v):
        return v//10 if v != 0xFFFF else FAKE_DISTANCE
    raw = {sid: (
        mm_to_cm(d8) if sid == 1 else
        mm_to_cm(d2) if sid == 2 else
        mm_to_cm(d3) if sid == 3 else
        FAKE_DISTANCE
    ) for sid in range(1,9)}
    print("[RAW]    " + ", ".join(f"S{sid}={raw[sid]}" for sid in range(1,9)))
    return raw

EMA_ALPHA = 0.7  # more responsive
ema = {sid: FAKE_DISTANCE for sid in range(1,9)}
ema2 = ema.copy()

def smooth(raw):
    for sid, val in raw.items():
        ema[sid] = EMA_ALPHA * val + (1-EMA_ALPHA) * ema[sid]
        ema2[sid] = EMA_ALPHA * ema[sid] + (1-EMA_ALPHA) * ema2[sid]
    filtered = {}
    for sid in raw:
        # Use either EMA or DEMA:
        filtered[sid] = int(2*ema[sid] - ema2[sid])
    print("[SMOOTHED]", filtered)
    return filtered

def send_distances(mav, dist):
    ts = time.time()
    print(f"[SEND @ {ts:.3f}]")
    for sid, d in dist.items():
        print(f"  • Sector {sid}: {d} cm → orient {SECTOR_ORIENTATION[sid]}")
        mav.mav.distance_sensor_send(
            time_boot_ms=0, min_distance=MIN_DISTANCE,
            max_distance=MAX_DISTANCE, current_distance=d,
            type=0, id=0, orientation=SECTOR_ORIENTATION[sid],
            covariance=0
        )

def main():
    rs = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)
    rs.reset_input_buffer()
    mav = mavutil.mavlink_connection(
        FC_PORT, baud=FC_BAUD, source_system=1, source_component=158
    )
    mav.wait_heartbeat()
    print("[DEBUG] Heartbeat OK. Starting loop…")

    last_hb = time.time()
    next_send = time.time()
    buf = bytearray()

    while True:
        if time.time() - last_hb >= 1.0:
            mav.mav.heartbeat_send(type=6, autopilot=8, base_mode=0,
                                   custom_mode=0, system_status=4)
            last_hb = time.time()

        buf += rs.read(rs.in_waiting or 1)
        offset = buf.find(b'TH')
        if offset < 0:
            if len(buf) > 200:
                buf.clear()
            continue
        if len(buf) - offset < 19:
            continue

        pkt = buf[offset:offset+19]
        buf = buf[offset+19:]
        raw = parse_packet(pkt)
        filtered = smooth(raw)

        if time.time() >= next_send:
            send_distances(mav, filtered)
            next_send += SEND_INTERVAL
            if time.time() > next_send:
                next_send = time.time()

if __name__ == '__main__':
    main()
