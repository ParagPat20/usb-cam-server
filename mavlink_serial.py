#!/usr/bin/env python3
import time
import platform
from pymavlink import mavutil

def find_mavlink_ports(baud=115200, timeout=1.0):
    '''
    Scan serial ports for MAVLink responders.
    Returns two lists: [ports with heartbeat], [the rest].
    '''
    heartbeat_ports = []
    other_ports = []
    
    # Detect OS and use appropriate port detection method
    if platform.system() == 'Windows':
        ports = mavutil.auto_detect_serial_windows()
    else:
        ports = mavutil.auto_detect_serial_unix()

    print(f"Scanning ports: {[p.device for p in ports]}")
    for p in ports:
        dev = p.device
        print(f"→ Testing {dev}...", end='', flush=True)
        try:
            m = mavutil.mavlink_connection(
                dev, baud=baud, timeout=timeout, autoreconnect=False
            )
            t0 = time.time()
            while time.time() - t0 < timeout:
                msg = m.recv_match(type='HEARTBEAT', blocking=False)
                if msg:
                    print(" HEARTBEAT!")
                    heartbeat_ports.append(dev)
                    m.close()
                    break
                time.sleep(0.1)
            else:
                print(" no heartbeat.")
                other_ports.append(dev)
                m.close()
        except Exception as e:
            print(f" error: {e}")
            other_ports.append(dev)

    return heartbeat_ports, other_ports

if __name__ == '__main__':
    fc_ports, sensor_ports = find_mavlink_ports()
    print()
    print("✅ MAVLink Flight Controller port(s):", fc_ports)
    print("🔍 Other detected port(s):", sensor_ports)
