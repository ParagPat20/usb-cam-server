import serial, time
from pymavlink import mavutil
from filterpy.kalman import KalmanFilter
import numpy as np
import threading
import sys

# Serial & MAVLink settings...
MR72_PORT, MR72_BAUD = '/dev/ttyS0', 115200
FC_PORT, FC_BAUD = '/dev/serial/by-id/usb-ArduPilot_Pixhawk6X_36004E001351333031333637-if00', 115200
FAKE_DISTANCE = 3000
MIN_DISTANCE, MAX_DISTANCE = 30, 3000
SECTOR_ORIENTATION = {2:0,1:1,8:2,7:3,6:4,5:5,4:6,3:7}
SEND_INTERVAL = 0.1  # 10 Hz
HEARTBEAT_INTERVAL = 0.5  # Increased heartbeat frequency to 2Hz
CONNECTION_TIMEOUT = 3.0  # Timeout for connection monitoring

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

# Connection monitoring
connection_stats = {
    'last_heartbeat_sent': 0,
    'last_distance_sent': 0,
    'connection_healthy': False,
    'reconnect_attempts': 0
}

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
    
    # Send distance sensor messages for each sector
    for sid, d in dist.items():
        try:
            mav.mav.distance_sensor_send(
                time_boot_ms=int(t * 1000),  # Use actual boot time
                min_distance=MIN_DISTANCE,
                max_distance=MAX_DISTANCE, 
                current_distance=int(d),
                type=0, 
                id=sid,  # Use sector ID as sensor ID
                orientation=SECTOR_ORIENTATION[sid],
                covariance=0
            )
        except Exception as e:
            print(f"[ERROR] Failed to send distance sensor for sector {sid}: {e}")
    
    # Send obstacle distance message for comprehensive coverage
    try:
        # Create 72-element array for 360° coverage (5° increments)
        distances = [10000] * 72  # Default to 100m (10000cm)
        
        # Fill in actual measurements where available
        for sid, d in dist.items():
            if sid in SECTOR_ORIENTATION:
                angle = SECTOR_ORIENTATION[sid] * 45  # Convert to degrees
                index = int(angle / 5) % 72  # Convert to 5° increments
                distances[index] = int(d)
        
        mav.mav.obstacle_distance_send(
            time_usec=int(t * 1000000),
            sensor_type=0,  # MAV_DISTANCE_SENSOR_LASER
            distances=distances,
            increment=5,  # 5° increments
            min_distance=MIN_DISTANCE,
            max_distance=MAX_DISTANCE,
            increment_f=5.0,
            angle_offset=0,
            frame=0  # MAV_FRAME_GLOBAL
        )
    except Exception as e:
        print(f"[ERROR] Failed to send obstacle distance: {e}")
    
    connection_stats['last_distance_sent'] = t

def send_heartbeat(mav):
    """Send heartbeat with proper system identification"""
    try:
        mav.mav.heartbeat_send(
            type=6,  # MAV_TYPE_GIMBAL
            autopilot=8,  # MAV_AUTOPILOT_PX4
            base_mode=0, 
            custom_mode=0, 
            system_status=4  # MAV_STATE_ACTIVE
        )
        connection_stats['last_heartbeat_sent'] = time.time()
        connection_stats['connection_healthy'] = True
    except Exception as e:
        print(f"[ERROR] Failed to send heartbeat: {e}")
        connection_stats['connection_healthy'] = False

def monitor_connection(mav):
    """Monitor connection health and attempt reconnection if needed"""
    while True:
        try:
            current_time = time.time()
            
            # Check if we need to reconnect
            if (current_time - connection_stats['last_heartbeat_sent'] > CONNECTION_TIMEOUT or 
                not connection_stats['connection_healthy']):
                
                print("[WARNING] Connection appears unhealthy, attempting reconnection...")
                connection_stats['reconnect_attempts'] += 1
                
                try:
                    # Try to re-establish connection
                    mav.close()
                    time.sleep(1)
                    mav = mavutil.mavlink_connection(FC_PORT, baud=FC_BAUD,
                                                   source_system=1, source_component=158)
                    mav.wait_heartbeat(timeout=5)
                    print("[INFO] Reconnection successful")
                    connection_stats['connection_healthy'] = True
                    connection_stats['reconnect_attempts'] = 0
                except Exception as e:
                    print(f"[ERROR] Reconnection failed: {e}")
                    connection_stats['connection_healthy'] = False
            
            time.sleep(1)
        except Exception as e:
            print(f"[ERROR] Connection monitor error: {e}")
            time.sleep(1)

def main():
    print("[INFO] Starting MR72 MAVLink bridge...")
    
    # Initialize serial connection
    try:
        rs = serial.Serial(MR72_PORT, MR72_BAUD, timeout=1)
        rs.reset_input_buffer()
        print(f"[INFO] Serial connection established on {MR72_PORT}")
    except Exception as e:
        print(f"[ERROR] Failed to open serial port {MR72_PORT}: {e}")
        sys.exit(1)
    
    # Initialize MAVLink connection
    try:
        mav = mavutil.mavlink_connection(FC_PORT, baud=FC_BAUD,
                                       source_system=1, source_component=158)
        mav.wait_heartbeat(timeout=10)
        print("[INFO] MAVLink connection established")
        connection_stats['connection_healthy'] = True
    except Exception as e:
        print(f"[ERROR] Failed to establish MAVLink connection: {e}")
        sys.exit(1)
    
    # Start connection monitoring in background thread
    monitor_thread = threading.Thread(target=monitor_connection, args=(mav,), daemon=True)
    monitor_thread.start()
    
    # Send initial heartbeat
    send_heartbeat(mav)
    
    last_hb = time.time()
    next_send = time.time()
    buf = bytearray()
    
    print("[INFO] Starting main loop...")
    
    while True:
        try:
            current_time = time.time()
            
            # Send heartbeat more frequently
            if current_time - last_hb >= HEARTBEAT_INTERVAL:
                send_heartbeat(mav)
                last_hb = current_time
            
            # Read serial data
            buf += rs.read(rs.in_waiting or 1)
            offset = buf.find(b'TH')
            if offset < 0:
                if len(buf) > 200: 
                    buf.clear()
                continue
            if len(buf) - offset < 19: 
                continue
            
            # Process packet
            pkt = buf[offset:offset+19]
            buf = buf[offset+19:]
            raw = parse_packet(pkt)
            filtered = smooth(raw)
            
            # Send distance data at regular intervals
            if current_time >= next_send:
                if connection_stats['connection_healthy']:
                    send_distances(mav, filtered)
                else:
                    print("[WARNING] Skipping distance send - connection unhealthy")
                next_send += SEND_INTERVAL
                if current_time > next_send:
                    next_send = current_time
                    
        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")
            break
        except Exception as e:
            print(f"[ERROR] Main loop error: {e}")
            time.sleep(1)
    
    # Cleanup
    try:
        rs.close()
        mav.close()
    except:
        pass
    print("[INFO] Shutdown complete")

if __name__ == "__main__":
    main()
