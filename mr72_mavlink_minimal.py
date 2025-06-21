#!/usr/bin/env python3
"""
Minimal MR72 Radar to MAVLink Bridge
Sends ALL sectors' data regardless of values
"""

import serial
import time
from pymavlink import mavutil

def parse_sector(frame, msb_index, lsb_index):
    if len(frame) != 19:
        return 0
    if frame[0] != 0x54 or frame[1] != 0x48:
        return 0
    msb, lsb = frame[msb_index], frame[lsb_index]
    val = (msb << 8) | lsb
    return val if val != 0xFFFF else 10000  # Return 10m if invalid

# Connect to flight controller
mav = mavutil.mavlink_connection('/dev/ttyACM0', baud=115200)
print("Waiting for MAVLink heartbeat...")
mav.wait_heartbeat()
print("MAVLink connected!")

# Connect to MR72 radar
ser = serial.Serial("/dev/ttyS0", 115200, timeout=1)
print("MR72 radar connected!")

boot_time = time.time()

def send_all_sectors(sector1, sector2, sector3, sector_90, sector_135, sector_180, sector_225, sector_270):
    time_boot_ms = int((time.time() - boot_time) * 1000) & 0xFFFFFFFF
    
    # Convert mm to cm
    def to_cm(val):
        return min(65535, max(0, val // 10))
    
    # Send ALL 8 sectors
    sectors = [
        (sector1, 1), (sector2, 2), (sector3, 3),
        (sector_90, 4), (sector_135, 5), (sector_180, 6),
        (sector_225, 7), (sector_270, 8)
    ]
    
    for distance, sensor_id in sectors:
        mav.mav.distance_sensor_send(
            time_boot_ms, 0, 1000, to_cm(distance), 0, sensor_id, 0, 255
        )

try:
    while True:
        frame = ser.read(19)
        if len(frame) == 19:
            # Parse ALL sectors
            sector2 = parse_sector(frame, 2, 3)   # D1
            sector3 = parse_sector(frame, 4, 5)   # D2
            sector_90 = parse_sector(frame, 6, 7)  # D3
            sector_135 = parse_sector(frame, 8, 9) # D4
            sector_180 = parse_sector(frame, 10, 11) # D5
            sector_225 = parse_sector(frame, 12, 13) # D6
            sector_270 = parse_sector(frame, 14, 15) # D7
            sector1 = parse_sector(frame, 16, 17)   # D8
            
            # Send ALL sectors to flight controller
            send_all_sectors(sector1, sector2, sector3, sector_90, sector_135, sector_180, sector_225, sector_270)
            
            # Print all sectors
            print(f"S1:{sector1} S2:{sector2} S3:{sector3} 90:{sector_90} 135:{sector_135} 180:{sector_180} 225:{sector_225} 270:{sector_270}")
            
        time.sleep(0.06)  # ~16.67Hz

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    ser.close()
    mav.close()
    print("Closed.") 