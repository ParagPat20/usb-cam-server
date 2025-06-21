#!/usr/bin/env python3
"""
MR72 Radar to MAVLink Bridge
Reads MR72 radar data from UART and sends it to flight controller via MAVLink
"""

import serial
import time
import threading
import logging
from pymavlink import mavutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MR72Radar:
    def __init__(self, uart_port="/dev/ttyS0", uart_baud=115200, 
                 mavlink_port="/dev/ttyACM0", mavlink_baud=115200):
        self.uart_port = uart_port
        self.uart_baud = uart_baud
        self.mavlink_port = mavlink_port
        self.mavlink_baud = mavlink_baud
        
        # MR72 Protocol constants
        self.HEADER = bytes([0x54, 0x48])  # 'TH'
        self.FRAME_LEN = 19
        self.INVALID_DISTANCE = 0xFFFF
        
        # Serial connections
        self.uart_ser = None
        self.mavlink_connection = None
        
        # Data storage
        self.latest_data = {
            'sector1': self.INVALID_DISTANCE,  # 0 degrees
            'sector2': self.INVALID_DISTANCE,  # 90 degrees  
            'sector3': self.INVALID_DISTANCE,  # 180 degrees
            'sector4': self.INVALID_DISTANCE,  # 270 degrees
            'sector5': self.INVALID_DISTANCE,  # 315 degrees
            'sector6': self.INVALID_DISTANCE,  # 45 degrees
        }
        
        # Threading
        self.running = False
        self.uart_thread = None
        self.mavlink_thread = None
        
        # MAVLink message counters
        self.distance_sensor_id = 0
        
    def connect_uart(self):
        """Connect to MR72 radar via UART"""
        try:
            self.uart_ser = serial.Serial(
                port=self.uart_port,
                baudrate=self.uart_baud,
                timeout=1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            logger.info(f"Connected to MR72 radar on {self.uart_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MR72 radar: {e}")
            return False
    
    def connect_mavlink(self):
        """Connect to flight controller via MAVLink"""
        try:
            # Connect to flight controller
            self.mavlink_connection = mavutil.mavlink_connection(
                f"serial:{self.mavlink_port}:{self.mavlink_baud}",
                source_system=1,
                source_component=1
            )
            
            # Wait for heartbeat
            self.mavlink_connection.wait_heartbeat()
            logger.info(f"Connected to flight controller on {self.mavlink_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to flight controller: {e}")
            return False
    
    def parse_mr72_frame(self, frame):
        """Parse MR72 radar frame according to protocol"""
        if len(frame) != self.FRAME_LEN:
            return None
        
        # Check header
        if frame[0:2] != self.HEADER:
            return None
        
        try:
            # Parse sectors according to protocol
            # D1: Sector 2 (90 degrees) - bytes 2-3
            sector2 = (frame[2] << 8) | frame[3]
            
            # D2: Sector 3 (180 degrees) - bytes 4-5  
            sector3 = (frame[4] << 8) | frame[5]
            
            # D3: 90 degree sector - bytes 6-7
            sector_90 = (frame[6] << 8) | frame[7]
            
            # D4: 135 degree sector - bytes 8-9
            sector_135 = (frame[8] << 8) | frame[9]
            
            # D5: 180 degree sector - bytes 10-11
            sector_180 = (frame[10] << 8) | frame[11]
            
            # D6: 225 degree sector - bytes 12-13
            sector_225 = (frame[12] << 8) | frame[13]
            
            # D7: 270 degree sector - bytes 14-15
            sector_270 = (frame[14] << 8) | frame[15]
            
            # D8: Sector 1 (0 degrees) - bytes 16-17
            sector1 = (frame[16] << 8) | frame[17]
            
            # Skip CRC8 check as requested
            
            return {
                'sector1': sector1 if sector1 != self.INVALID_DISTANCE else None,
                'sector2': sector2 if sector2 != self.INVALID_DISTANCE else None,
                'sector3': sector3 if sector3 != self.INVALID_DISTANCE else None,
                'sector_90': sector_90 if sector_90 != self.INVALID_DISTANCE else None,
                'sector_135': sector_135 if sector_135 != self.INVALID_DISTANCE else None,
                'sector_180': sector_180 if sector_180 != self.INVALID_DISTANCE else None,
                'sector_225': sector_225 if sector_225 != self.INVALID_DISTANCE else None,
                'sector_270': sector_270 if sector_270 != self.INVALID_DISTANCE else None,
            }
            
        except Exception as e:
            logger.error(f"Error parsing MR72 frame: {e}")
            return None
    
    def send_distance_sensor_mavlink(self, distance_mm, orientation, sensor_id):
        """Send distance sensor data via MAVLink"""
        if not self.mavlink_connection:
            return
        
        try:
            # Convert mm to cm for MAVLink
            distance_cm = distance_mm / 10.0
            
            # Send DISTANCE_SENSOR message
            self.mavlink_connection.mav.distance_sensor_send(
                time_boot_ms=int(time.time() * 1000),
                min_distance=10,  # 10cm minimum
                max_distance=10000,  # 100m maximum
                current_distance=int(distance_cm),
                type=0,  # MAV_DISTANCE_SENSOR_ULTRASOUND
                id=sensor_id,
                orientation=orientation,
                covariance=0
            )
            
        except Exception as e:
            logger.error(f"Error sending distance sensor data: {e}")
    
    def send_obstacle_distance_mavlink(self, distances):
        """Send OBSTACLE_DISTANCE message for all sectors"""
        if not self.mavlink_connection:
            return
        
        try:
            # Create distance array (72 elements for 5-degree increments)
            # Initialize with maximum distance (10000cm = 100m)
            distance_array = [10000] * 72
            
            # Map our sectors to the 72-element array
            # Each sector covers approximately 56 degrees, but we'll map to closest 5-degree increments
            
            # Sector 1 (0 degrees) - map to indices around 0
            if distances['sector1'] is not None:
                for i in range(6):  # ±15 degrees around 0
                    idx = (i + 72) % 72
                    distance_array[idx] = distances['sector1'] // 10  # Convert to cm
            
            # Sector 2 (90 degrees) - map to indices around 18
            if distances['sector2'] is not None:
                for i in range(6):  # ±15 degrees around 90
                    idx = (18 + i) % 72
                    distance_array[idx] = distances['sector2'] // 10  # Convert to cm
            
            # Sector 3 (180 degrees) - map to indices around 36
            if distances['sector3'] is not None:
                for i in range(6):  # ±15 degrees around 180
                    idx = (36 + i) % 72
                    distance_array[idx] = distances['sector3'] // 10  # Convert to cm
            
            # Send OBSTACLE_DISTANCE message
            self.mavlink_connection.mav.obstacle_distance_send(
                time_usec=int(time.time() * 1000000),
                sensor_type=0,  # MAV_DISTANCE_SENSOR_ULTRASOUND
                distances=distance_array,
                increment=5,  # 5-degree increments
                min_distance=10,  # 10cm
                max_distance=10000,  # 100m
                increment_f=5.0,
                angle_offset=0.0,
                frame=12  # MAV_FRAME_BODY_FRD
            )
            
        except Exception as e:
            logger.error(f"Error sending obstacle distance data: {e}")
    
    def uart_reader_thread(self):
        """Thread to continuously read UART data from MR72"""
        buffer = b''
        
        while self.running:
            try:
                if self.uart_ser and self.uart_ser.is_open:
                    # Read available data
                    data = self.uart_ser.read(64)
                    if data:
                        buffer += data
                        
                        # Process complete frames
                        while len(buffer) >= self.FRAME_LEN:
                            # Look for header
                            if buffer[0:2] == self.HEADER:
                                # Extract frame
                                frame = buffer[:self.FRAME_LEN]
                                buffer = buffer[self.FRAME_LEN:]
                                
                                # Parse frame
                                parsed_data = self.parse_mr72_frame(frame)
                                if parsed_data:
                                    # Update latest data
                                    with threading.Lock():
                                        self.latest_data.update(parsed_data)
                                    
                                    logger.debug(f"MR72 Data: {parsed_data}")
                            else:
                                # Remove invalid byte
                                buffer = buffer[1:]
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in UART reader thread: {e}")
                time.sleep(1)
    
    def mavlink_sender_thread(self):
        """Thread to continuously send data to flight controller"""
        while self.running:
            try:
                if self.mavlink_connection:
                    # Send individual distance sensor messages for sectors 1, 2, 3
                    with threading.Lock():
                        data = self.latest_data.copy()
                    
                    # Send sector 1 (0 degrees)
                    if data['sector1'] is not None:
                        self.send_distance_sensor_mavlink(
                            data['sector1'], 
                            0,  # MAV_SENSOR_ROTATION_NONE
                            1
                        )
                    
                    # Send sector 2 (90 degrees)
                    if data['sector2'] is not None:
                        self.send_distance_sensor_mavlink(
                            data['sector2'], 
                            1,  # MAV_SENSOR_ROTATION_90_DEG
                            2
                        )
                    
                    # Send sector 3 (180 degrees)
                    if data['sector3'] is not None:
                        self.send_distance_sensor_mavlink(
                            data['sector3'], 
                            2,  # MAV_SENSOR_ROTATION_180_DEG
                            3
                        )
                    
                    # Send comprehensive obstacle distance message
                    self.send_obstacle_distance_mavlink(data)
                    
                time.sleep(0.1)  # 10Hz update rate
                
            except Exception as e:
                logger.error(f"Error in MAVLink sender thread: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the MR72 radar bridge"""
        logger.info("Starting MR72 radar bridge...")
        
        # Connect to UART
        if not self.connect_uart():
            logger.error("Failed to connect to UART")
            return False
        
        # Connect to MAVLink
        if not self.connect_mavlink():
            logger.error("Failed to connect to MAVLink")
            return False
        
        # Start threads
        self.running = True
        
        self.uart_thread = threading.Thread(target=self.uart_reader_thread, daemon=True)
        self.uart_thread.start()
        
        self.mavlink_thread = threading.Thread(target=self.mavlink_sender_thread, daemon=True)
        self.mavlink_thread.start()
        
        logger.info("MR72 radar bridge started successfully")
        return True
    
    def stop(self):
        """Stop the MR72 radar bridge"""
        logger.info("Stopping MR72 radar bridge...")
        self.running = False
        
        # Close connections
        if self.uart_ser:
            self.uart_ser.close()
        
        if self.mavlink_connection:
            self.mavlink_connection.close()
        
        logger.info("MR72 radar bridge stopped")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MR72 Radar to MAVLink Bridge")
    parser.add_argument("--uart-port", default="/dev/ttyS0", help="UART port for MR72 radar")
    parser.add_argument("--uart-baud", type=int, default=115200, help="UART baud rate")
    parser.add_argument("--mavlink-port", default="/dev/ttyACM1", help="MAVLink port for flight controller")
    parser.add_argument("--mavlink-baud", type=int, default=115200, help="MAVLink baud rate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start radar bridge
    radar = MR72Radar(
        uart_port=args.uart_port,
        uart_baud=args.uart_baud,
        mavlink_port=args.mavlink_port,
        mavlink_baud=args.mavlink_baud
    )
    
    try:
        if radar.start():
            logger.info("MR72 radar bridge running. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        else:
            logger.error("Failed to start MR72 radar bridge")
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        radar.stop()

if __name__ == "__main__":
    main() 