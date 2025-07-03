#!/usr/bin/env python3
"""
MAVLink Diagnostics Tool for MR72 Radar Bridge
Helps diagnose connection issues and PRX1 data problems
"""

import time
import sys
from pymavlink import mavutil
from pymavlink import mavlink

def check_mavlink_connection(port, baud=115200):
    """Test MAVLink connection and message flow"""
    print(f"[INFO] Testing MAVLink connection on {port} at {baud} baud...")
    
    try:
        # Try to connect
        mav = mavutil.mavlink_connection(port, baud=baud, source_system=1, source_component=158)
        
        # Wait for heartbeat
        print("[INFO] Waiting for heartbeat...")
        mav.wait_heartbeat(timeout=10)
        print("[SUCCESS] Heartbeat received!")
        
        # Get system info
        system_id = mav.target_system
        component_id = mav.target_component
        print(f"[INFO] Connected to System ID: {system_id}, Component ID: {component_id}")
        
        # Monitor messages for a few seconds
        print("[INFO] Monitoring MAVLink messages for 10 seconds...")
        start_time = time.time()
        message_count = 0
        distance_messages = 0
        heartbeat_count = 0
        
        while time.time() - start_time < 10:
            try:
                msg = mav.recv_match(blocking=True, timeout=1)
                if msg is not None:
                    message_count += 1
                    msg_type = msg.get_type()
                    
                    if msg_type == 'HEARTBEAT':
                        heartbeat_count += 1
                        print(f"[MSG] Heartbeat from {msg.get_srcSystem()}.{msg.get_srcComponent()}")
                    
                    elif msg_type == 'DISTANCE_SENSOR':
                        distance_messages += 1
                        print(f"[MSG] Distance Sensor: ID={msg.id}, Distance={msg.current_distance}cm, Orientation={msg.orientation}")
                    
                    elif msg_type == 'OBSTACLE_DISTANCE':
                        print(f"[MSG] Obstacle Distance: {len(msg.distances)} measurements")
                    
                    # Print other message types occasionally
                    elif message_count % 10 == 0:
                        print(f"[MSG] {msg_type}")
                        
            except Exception as e:
                print(f"[ERROR] Message receive error: {e}")
                break
        
        print(f"\n[SUMMARY] Message Statistics:")
        print(f"  Total messages: {message_count}")
        print(f"  Heartbeats: {heartbeat_count}")
        print(f"  Distance sensor messages: {distance_messages}")
        
        if distance_messages == 0:
            print("[WARNING] No distance sensor messages received!")
            print("[WARNING] This could explain the 'No PRX1 Data found' error")
        
        mav.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return False

def test_distance_sensor_sending(port, baud=115200):
    """Test sending distance sensor messages"""
    print(f"\n[INFO] Testing distance sensor message sending...")
    
    try:
        mav = mavutil.mavlink_connection(port, baud=baud, source_system=1, source_component=158)
        mav.wait_heartbeat(timeout=10)
        
        # Send test distance sensor messages
        for i in range(5):
            try:
                # Send distance sensor message for sector 1
                mav.mav.distance_sensor_send(
                    time_boot_ms=int(time.time() * 1000),
                    min_distance=30,
                    max_distance=3000,
                    current_distance=100 + i * 50,  # Varying distance
                    type=0,  # MAV_DISTANCE_SENSOR_LASER
                    id=1,    # Sensor ID
                    orientation=1,  # MAV_SENSOR_ROTATION_NONE
                    covariance=0
                )
                print(f"[SEND] Distance sensor message {i+1}: 100+{i*50}cm")
                time.sleep(0.2)
                
            except Exception as e:
                print(f"[ERROR] Failed to send distance sensor message: {e}")
        
        # Send obstacle distance message
        try:
            distances = [1000] * 72  # 1000cm for all directions
            mav.mav.obstacle_distance_send(
                time_usec=int(time.time() * 1000000),
                sensor_type=0,
                distances=distances,
                increment=5,
                min_distance=30,
                max_distance=3000,
                increment_f=5.0,
                angle_offset=0,
                frame=0
            )
            print("[SEND] Obstacle distance message sent")
        except Exception as e:
            print(f"[ERROR] Failed to send obstacle distance: {e}")
        
        mav.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Distance sensor test failed: {e}")
        return False

def check_serial_ports():
    """Check available serial ports"""
    print("[INFO] Checking available serial ports...")
    
    import glob
    import os
    
    # Common serial port patterns
    patterns = [
        '/dev/ttyS*',
        '/dev/ttyUSB*', 
        '/dev/ttyACM*',
        '/dev/serial/by-id/*'
    ]
    
    found_ports = []
    for pattern in patterns:
        ports = glob.glob(pattern)
        for port in ports:
            if os.path.exists(port):
                found_ports.append(port)
    
    if found_ports:
        print("[INFO] Found serial ports:")
        for port in found_ports:
            print(f"  {port}")
    else:
        print("[WARNING] No serial ports found!")
    
    return found_ports

def main():
    print("=" * 60)
    print("MAVLink Diagnostics Tool for MR72 Radar Bridge")
    print("=" * 60)
    
    # Check available ports
    ports = check_serial_ports()
    
    # Test specific ports
    test_ports = [
        '/dev/ttyS0',
        '/dev/serial/by-id/usb-ArduPilot_Pixhawk6X_36004E001351333031333637-if00',
        '/dev/ttyACM0',
        '/dev/ttyUSB0'
    ]
    
    print(f"\n[INFO] Testing MAVLink connections...")
    
    for port in test_ports:
        if port in ports or port.startswith('/dev/serial/'):
            print(f"\n{'='*40}")
            print(f"Testing: {port}")
            print(f"{'='*40}")
            
            if check_mavlink_connection(port):
                print(f"[SUCCESS] {port} is working!")
                
                # Test sending messages
                if test_distance_sensor_sending(port):
                    print(f"[SUCCESS] Distance sensor messages sent successfully on {port}")
                else:
                    print(f"[ERROR] Failed to send distance sensor messages on {port}")
            else:
                print(f"[FAILED] {port} is not working")
        else:
            print(f"[SKIP] {port} not found")
    
    print(f"\n{'='*60}")
    print("Diagnostics Complete")
    print("=" * 60)
    
    print("\n[TROUBLESHOOTING TIPS]")
    print("1. If no distance sensor messages are received, check:")
    print("   - MR72 radar is powered and connected")
    print("   - Serial port permissions (add user to dialout group)")
    print("   - MAVLink message routing in your GCS")
    print("2. For 'No PRX1 Data found' errors:")
    print("   - Ensure distance sensor messages are being sent regularly")
    print("   - Check GCS configuration for PRX1 sensor")
    print("   - Verify MAVLink message routing between components")
    print("3. For network connectivity issues:")
    print("   - Check WiFi/Ethernet connection")
    print("   - Restart the MR72 bridge after network reconnection")
    print("   - Monitor connection logs for reconnection attempts")

if __name__ == "__main__":
    main() 