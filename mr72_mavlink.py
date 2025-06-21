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
import array

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
        
        # Track boot time for proper time_boot_ms calculation
        self.boot_time = time.time()
        
        # Data storage
        self.latest_data = {
            'sector1': None,  # 0 degrees
            'sector2': None,  # 90 degrees  
            'sector3': None,  # 180 degrees
            'sector_90': None,  # 90 degree sector
            'sector_135': None,  # 135 degree sector
            'sector_180': None,  # 180 degree sector
            'sector_225': None,  # 225 degree sector
            'sector_270': None,  # 270 degree sector
        }
        
        # Threading
        self.running = False
        self.uart_thread = None
        self.mavlink_thread = None
        
    def parse_sector(self, frame, msb_index, lsb_index):
        """Parse individual sector from MR72 frame"""
        if len(frame) != self.FRAME_LEN:
            return None
        # Check header
        if frame[0] != 0x54 or frame[1] != 0x48:
            return None
        msb, lsb = frame[msb_index], frame[lsb_index]
        val = (msb << 8) | lsb
        if val == 0xFFFF:
            return None  # Invalid data
        return val
        
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
            logger.info(f"Attempting to connect to MAVLink on: {self.mavlink_port} at {self.mavlink_baud} baud")
            self.mavlink_connection = mavutil.mavlink_connection(
                self.mavlink_port,
                baud=self.mavlink_baud
            )
            
            # Wait for heartbeat with timeout
            logger.info("Waiting for flight controller heartbeat...")
            try:
                self.mavlink_connection.wait_heartbeat()
                logger.info(f"Connected to flight controller on {self.mavlink_port}")
                return True
            except Exception as e:
                logger.error(f"Timeout waiting for heartbeat: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to flight controller: {e}")
            return False
    
    def send_distance_data(self, sector1, sector2, sector3, sector_90, sector_135, sector_180, sector_225, sector_270):
        """Send distance sensor data via MAVLink"""
        if not self.mavlink_connection:
            return
        
        try:
            # Calculate time since boot in milliseconds
            time_boot_ms = int((time.time() - self.boot_time) * 1000) & 0xFFFFFFFF
            
            # Convert mm to cm and ensure values are within bounds
            def safe_convert(val):
                if val is None:
                    return 0
                # Convert to cm and ensure it's within uint16 range (0-65535)
                return min(65535, max(0, val // 10))
            
            # Common parameters
            min_distance = 0  # Minimum distance the sensor can measure in cm
            max_distance = 1000  # Maximum distance the sensor can measure in cm
            max_distance_cm = 10000  # Maximum distance placeholder (100m)
            
            # Send each sector as a separate DISTANCE_SENSOR message
            # Sector 1 (0 degrees)
            self.mavlink_connection.mav.distance_sensor_send(
                time_boot_ms,  # ms since system boot
                min_distance,  # Minimum distance in cm
                max_distance,  # Maximum distance in cm
                safe_convert(sector1) if sector1 is not None else max_distance_cm,  # Current distance reading
                0,  # Sensor type (0 = MAV_DISTANCE_SENSOR_LASER)
                1,  # Sensor ID (1 for sector 1)
                0,  # Orientation (0 = MAV_SENSOR_ROTATION_NONE for forward)
                255  # Covariance in cm (255 if unknown)
            )
            
            # Sector 2 (90 degrees)
            self.mavlink_connection.mav.distance_sensor_send(
                time_boot_ms,
                min_distance,
                max_distance,
                safe_convert(sector2) if sector2 is not None else max_distance_cm,
                0,  # Sensor type (0 = MAV_DISTANCE_SENSOR_LASER)
                2,  # Sensor ID (2 for sector 2)
                0,  # Orientation (0 = MAV_SENSOR_ROTATION_NONE for forward)
                255  # Covariance in cm (255 if unknown)
            )
            
            # Sector 3 (180 degrees)
            self.mavlink_connection.mav.distance_sensor_send(
                time_boot_ms,
                min_distance,
                max_distance,
                safe_convert(sector3) if sector3 is not None else max_distance_cm,
                0,  # Sensor type (0 = MAV_DISTANCE_SENSOR_LASER)
                3,  # Sensor ID (3 for sector 3)
                0,  # Orientation (0 = MAV_SENSOR_ROTATION_NONE for forward)
                255  # Covariance in cm (255 if unknown)
            )
            
            # Other sectors as placeholders with maximum distance
            # Sector 90 degrees
            self.mavlink_connection.mav.distance_sensor_send(
                time_boot_ms, min_distance, max_distance, 
                safe_convert(sector_90) if sector_90 is not None else max_distance_cm,
                0, 4, 0, 255  # Sensor ID 4
            )
            
            # Sector 135 degrees
            self.mavlink_connection.mav.distance_sensor_send(
                time_boot_ms, min_distance, max_distance, 
                safe_convert(sector_135) if sector_135 is not None else max_distance_cm,
                0, 5, 0, 255  # Sensor ID 5
            )
            
            # Sector 180 degrees
            self.mavlink_connection.mav.distance_sensor_send(
                time_boot_ms, min_distance, max_distance, 
                safe_convert(sector_180) if sector_180 is not None else max_distance_cm,
                0, 6, 0, 255  # Sensor ID 6
            )
            
            # Sector 225 degrees
            self.mavlink_connection.mav.distance_sensor_send(
                time_boot_ms, min_distance, max_distance, 
                safe_convert(sector_225) if sector_225 is not None else max_distance_cm,
                0, 7, 0, 255  # Sensor ID 7
            )
            
            # Sector 270 degrees
            self.mavlink_connection.mav.distance_sensor_send(
                time_boot_ms, min_distance, max_distance, 
                safe_convert(sector_270) if sector_270 is not None else max_distance_cm,
                0, 8, 0, 255  # Sensor ID 8
            )
            
        except Exception as e:
            logger.error(f"Error sending distance sensor data: {e}")
    
    def uart_reader_thread(self):
        """Thread to continuously read UART data from MR72"""
        while self.running:
            try:
                if self.uart_ser and self.uart_ser.is_open:
                    frame = self.uart_ser.read(19)
                    if len(frame) == 19:  # Make sure we got a complete frame
                        # Parse sectors according to protocol
                        sector2 = self.parse_sector(frame, 2, 3)  # D1: Sector 2 (90 degrees)
                        sector3 = self.parse_sector(frame, 4, 5)  # D2: Sector 3 (180 degrees)
                        sector_90 = self.parse_sector(frame, 6, 7)  # D3: 90 degree sector
                        sector_135 = self.parse_sector(frame, 8, 9)  # D4: 135 degree sector
                        sector_180 = self.parse_sector(frame, 10, 11)  # D5: 180 degree sector
                        sector_225 = self.parse_sector(frame, 12, 13)  # D6: 225 degree sector
                        sector_270 = self.parse_sector(frame, 14, 15)  # D7: 270 degree sector
                        sector1 = self.parse_sector(frame, 16, 17)  # D8: Sector 1 (0 degrees)
                        
                        # Update latest data
                        with threading.Lock():
                            self.latest_data = {
                                'sector1': sector1,
                                'sector2': sector2,
                                'sector3': sector3,
                                'sector_90': sector_90,
                                'sector_135': sector_135,
                                'sector_180': sector_180,
                                'sector_225': sector_225,
                                'sector_270': sector_270,
                            }
                        
                        logger.debug(f"MR72 Data: {self.latest_data}")
                        
                        # Display data
                        output = []
                        if sector1 is not None:
                            output.append(f"Sector 1: {sector1} mm")
                        if sector2 is not None:
                            output.append(f"Sector 2: {sector2} mm")
                        if sector3 is not None:
                            output.append(f"Sector 3: {sector3} mm")
                        if output:
                            logger.info(" | ".join(output))
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
                    # Send individual distance sensor messages for all sectors
                    with threading.Lock():
                        data = self.latest_data.copy()
                    
                    # Send distance sensor data
                    self.send_distance_data(
                        data['sector1'], data['sector2'], data['sector3'],
                        data['sector_90'], data['sector_135'], data['sector_180'],
                        data['sector_225'], data['sector_270']
                    )
                    
                    # Note: OBSTACLE_DISTANCE message removed as it's not available in this pymavlink version
                    # The DISTANCE_SENSOR messages provide sufficient obstacle detection data
                    
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
    parser.add_argument("--mavlink-port", default="/dev/ttyACM0", help="MAVLink port for flight controller")
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