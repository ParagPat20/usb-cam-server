#!/usr/bin/env python3
from pymavlink import mavutil
import glob, time

BAUD = 115200
TIMEOUT = 2.0

def find_fc_port():
    print("Scanning ID paths for MAVLink-enabled Flight Controller...")
    for path in glob.glob('/dev/serial/by-id/*'):
        print(f"→ Testing {path}...", end='', flush=True)
        try:
            m = mavutil.mavlink_connection(path, baud=BAUD, timeout=TIMEOUT)
            msg = m.recv_match(type='HEARTBEAT', blocking=True, timeout=TIMEOUT)
            if msg:
                print(" HEARTBEAT received!")
                m.close()
                return path
            else:
                print(" no heartbeat.")
            m.close()
        except Exception as e:
            print(f" error: {e}")
    return None

if __name__ == '__main__':
    fc = find_fc_port()
    others = [p for p in glob.glob('/dev/serial/by-id/*') if p != fc]
    print("\n✅ Detected Flight Controller port:", fc or "None")
    print("🔍 Other serial ports:", others)
