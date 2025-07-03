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
SEND_INTERVAL = 0.05  # 10 Hz
RECONNECT_DELAY = 2.0  # seconds to wait before reconnecting

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
    return raw

def smooth(raw):
    smoothed = {}
    for sid, meas in raw.items():
        kf = filters[sid]
        kf.predict()
        kf.update(np.array([[meas]]))
        smoothed[sid] = float(kf.x)
    return smoothed

def send_distances(mav, dist):
    global last_send_time
    current_time = time.time()
    
    if 'last_send_time' in globals():
        interval = current_time - last_send_time
        frequency = 1.0 / interval if interval > 0 else 0
        print(f"[FREQ] Send interval: {interval*1000:.1f}ms ({frequency:.1f} Hz)")
    
    last_send_time = current_time
    print(f"[SEND @ {current_time:.3f}]" + ", ".join(f"S{sid}:{int(dist[sid])}cm" for sid in sorted(dist)))
    
    for sid, d in dist.items():
        try:
            mav.mav.distance_sensor_send(
                time_boot_ms=0, min_distance=MIN_DISTANCE,
                max_distance=MAX_DISTANCE, current_distance=int(d),
                type=0, id=sid,  # Use sector ID as sensor ID
                orientation=SECTOR_ORIENTATION[sid],
                covariance=0
            )
        except Exception as e:
            print(f"[ERROR] Failed to send distance for sector {sid}: {e}")

def connect_serial():
    """Connect to MR72 with retry logic"""
    while True:
        try:
            rs = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)
            rs.reset_input_buffer()
            print(f"[DEBUG] Connected to MR72 on {MR72_PORT}")
            return rs
        except Exception as e:
            print(f"[ERROR] Failed to connect to MR72: {e}")
            print(f"[DEBUG] Retrying in {RECONNECT_DELAY} seconds...")
            time.sleep(RECONNECT_DELAY)

def connect_mavlink():
    """Connect to FC with retry logic"""
    while True:
        try:
            mav = mavutil.mavlink_connection(FC_PORT, baud=FC_BAUD,
                                           source_system=1, source_component=158)
            mav.wait_heartbeat(timeout=5.0)
            print(f"[DEBUG] Connected to FC on {FC_PORT}")
            return mav
        except Exception as e:
            print(f"[ERROR] Failed to connect to FC: {e}")
            print(f"[DEBUG] Retrying in {RECONNECT_DELAY} seconds...")
            time.sleep(RECONNECT_DELAY)

def main():
    print("[DEBUG] Starting MR72 MAVLink bridge...")
    
    # Initial connections
    rs = connect_serial()
    mav = connect_mavlink()
    
    last_hb = time.time()
    next_send = time.time()
    last_data_time = time.time()

    buf = bytearray()
    while True:
        try:
            # Send heartbeat
            if time.time() - last_hb >= 1.0:
                try:
                    mav.mav.heartbeat_send(type=6, autopilot=8,
                                           base_mode=0, custom_mode=0, system_status=4)
                    last_hb = time.time()
                except Exception as e:
                    print(f"[ERROR] Failed to send heartbeat: {e}")
                    print("[DEBUG] Reconnecting to FC...")
                    mav = connect_mavlink()

            # Read serial data with timeout
            try:
                data = rs.read(rs.in_waiting or 1)
                if data:
                    last_data_time = time.time()
                    buf += data
            except Exception as e:
                print(f"[ERROR] Serial read failed: {e}")
                print("[DEBUG] Reconnecting to MR72...")
                rs = connect_serial()
                buf.clear()
                continue

            # Check for data timeout
            if time.time() - last_data_time > 5.0:
                print("[WARNING] No data from MR72 for 5 seconds")
                last_data_time = time.time()

            # Parse packets
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

            # Send distances
            if time.time() >= next_send:
                send_distances(mav, filtered)
                next_send += SEND_INTERVAL
                if time.time() > next_send:
                    next_send = time.time()

        except KeyboardInterrupt:
            print("\n[DEBUG] Shutting down...")
            break
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            time.sleep(1)

    # Cleanup
    try:
        rs.close()
    except:
        pass
    try:
        mav.close()
    except:
        pass

if __name__ == "__main__":
    main()
