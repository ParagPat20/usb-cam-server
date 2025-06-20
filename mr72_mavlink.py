#!/usr/bin/env python3
"""
MR72 Radar to MAVLink Integration
Reads MR72 radar data from ttyS0 and sends proximity data to flight controller via MAVLink
"""

import serial
import socket
import struct
import time
import logging
import threading
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MR72Radar:
    """MR72 Radar UART Protocol Handler"""
    
    def __init__(self, port="/dev/ttyS0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = False
        
        # MR72 Protocol constants
        self.HEADER = bytes([0x54, 0x48])  # 'T' 'H' in ASCII
        self.FRAME_LENGTH = 19  # Total frame length including CRC
        self.CRC_LENGTH = 1
        
        # Sector definitions
        self.SECTORS = {
            'sector1': {'index': 16, 'name': 'Sector 1 (0-56°)'},
            'sector2': {'index': 2, 'name': 'Sector 2 (56-112°)'},
            'sector3': {'index': 4, 'name': 'Sector 3 (112-168°)'},
            'obstacle_90': {'index': 6, 'name': 'Obstacle 90°'},
            'obstacle_135': {'index': 8, 'name': 'Obstacle 135°'},
            'obstacle_180': {'index': 10, 'name': 'Obstacle 180°'},
            'obstacle_225': {'index': 12, 'name': 'Obstacle 225°'},
            'obstacle_270': {'index': 14, 'name': 'Obstacle 270°'}
        }
        
        self.latest_data = {}
        self.data_lock = threading.Lock()
    
    def crc8_calc(self, data: bytes) -> int:
        """Calculate CRC8 for data validation"""
        crc = 0
        for byte in data[:-1]:  # Exclude the CRC byte itself
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x31
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc
    
    def parse_sector_distance(self, frame: bytes, msb_index: int, lsb_index: int) -> Optional[int]:
        """Parse 2-byte sector distance (high byte first, low byte last)"""
        if len(frame) < max(msb_index, lsb_index) + 1:
            return None
        
        msb, lsb = frame[msb_index], frame[lsb_index]
        distance = (msb << 8) | lsb
        
        # Check for invalid data (0xFFFF)
        if distance == 0xFFFF:
            return None
        
        return distance
    
    def parse_frame(self, frame: bytes) -> Optional[dict]:
        """Parse complete MR72 frame according to protocol"""
        if len(frame) != self.FRAME_LENGTH:
            logger.warning(f"Invalid frame length: {len(frame)} (expected {self.FRAME_LENGTH})")
            return None
        
        # Check header
        if frame[0:2] != self.HEADER:
            logger.warning(f"Invalid header: {frame[0:2].hex()} (expected {self.HEADER.hex()})")
            return None
        
        # Verify CRC
        calculated_crc = self.crc8_calc(frame)
        received_crc = frame[-1]
        if calculated_crc != received_crc:
            logger.warning(f"CRC mismatch: calculated={calculated_crc:02X}, received={received_crc:02X}")
            return None
        
        # Parse all sectors
        data = {}
        for sector_name, sector_info in self.SECTORS.items():
            distance = self.parse_sector_distance(frame, sector_info['index'], sector_info['index'] + 1)
            data[sector_name] = distance
        
        return data
    
    def open_serial(self) -> bool:
        """Open serial connection to MR72 radar"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            logger.info(f"Successfully opened serial connection to {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to open serial connection: {e}")
            return False
    
    def close_serial(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("Serial connection closed")
    
    def read_frames(self):
        """Read and parse MR72 frames continuously"""
        buffer = b''
        
        while self.running:
            try:
                if not self.ser or not self.ser.is_open:
                    logger.error("Serial connection not available")
                    time.sleep(1)
                    continue
                
                # Read available data
                data = self.ser.read(64)
                if not data:
                    continue
                
                buffer += data
                
                # Process complete frames
                while len(buffer) >= self.FRAME_LENGTH:
                    # Look for header
                    header_pos = buffer.find(self.HEADER)
                    if header_pos == -1:
                        # No header found, discard buffer
                        buffer = b''
                        break
                    
                    # Remove data before header
                    if header_pos > 0:
                        buffer = buffer[header_pos:]
                    
                    # Check if we have a complete frame
                    if len(buffer) < self.FRAME_LENGTH:
                        break
                    
                    # Extract frame
                    frame = buffer[:self.FRAME_LENGTH]
                    buffer = buffer[self.FRAME_LENGTH:]
                    
                    # Parse frame
                    parsed_data = self.parse_frame(frame)
                    if parsed_data:
                        with self.data_lock:
                            self.latest_data = parsed_data
                        logger.debug(f"Parsed radar data: {parsed_data}")
                
            except Exception as e:
                logger.error(f"Error reading radar data: {e}")
                time.sleep(0.1)
    
    def get_latest_data(self) -> dict:
        """Get the latest parsed radar data"""
        with self.data_lock:
            return self.latest_data.copy()
    
    def start(self):
        """Start radar reading thread"""
        if not self.open_serial():
            return False
        
        self.running = True
        self.read_thread = threading.Thread(target=self.read_frames, daemon=True)
        self.read_thread.start()
        logger.info("MR72 radar reading started")
        return True
    
    def stop(self):
        """Stop radar reading"""
        self.running = False
        self.close_serial()
        logger.info("MR72 radar reading stopped")


class MAVLinkSender:
    """MAVLink message sender for proximity data"""
    
    def __init__(self, host="127.0.0.1", port=14551):
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        
        # MAVLink message IDs
        self.MAVLINK_MSG_ID_DISTANCE_SENSOR = 132
        self.MAVLINK_MSG_ID_OBSTACLE_DISTANCE = 330
        
        # System and component IDs
        self.SYSTEM_ID = 1
        self.COMPONENT_ID = 1
    
    def create_mavlink_header(self, msg_id: int, payload_length: int) -> bytes:
        """Create MAVLink v1.0 message header"""
        # MAVLink v1.0 header: 6 bytes
        # [0] = 0xFE (magic marker)
        # [1] = payload length
        # [2] = sequence number (we'll use 0)
        # [3] = system ID
        # [4] = component ID
        # [5] = message ID
        return struct.pack('<BBBBBB', 0xFE, payload_length, 0, self.SYSTEM_ID, self.COMPONENT_ID, msg_id)
    
    def calculate_checksum(self, message: bytes) -> int:
        """Calculate MAVLink checksum"""
        crc = 0xFFFF
        for byte in message[1:]:  # Skip magic marker
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return crc
    
    def send_distance_sensor(self, distance_cm: int, sensor_type: int = 0, orientation: int = 0):
        """Send DISTANCE_SENSOR message"""
        if distance_cm is None or distance_cm <= 0:
            return
        
        # DISTANCE_SENSOR message payload (16 bytes)
        # time_boot_ms, min_distance, max_distance, current_distance, type, id, orientation, covariance
        payload = struct.pack('<IIIIBBBB',
            int(time.time() * 1000),  # time_boot_ms
            0,                        # min_distance (cm)
            10000,                    # max_distance (cm) - 100m
            distance_cm,              # current_distance (cm)
            sensor_type,              # type (0 = laser)
            0,                        # id
            orientation,              # orientation
            0                         # covariance
        )
        
        header = self.create_mavlink_header(self.MAVLINK_MSG_ID_DISTANCE_SENSOR, len(payload))
        message = header + payload
        checksum = self.calculate_checksum(message)
        message += struct.pack('<H', checksum)
        
        self.send_message(message)
    
    def send_obstacle_distance(self, distances: list):
        """Send OBSTACLE_DISTANCE message"""
        # OBSTACLE_DISTANCE message payload (72 bytes)
        # time_usec, sensor_type, distances[72], increment, min_distance, max_distance, increment_f, angle_offset, frame
        payload = struct.pack('<QBB', 
            int(time.time() * 1000000),  # time_usec
            0,                           # sensor_type (0 = laser)
            0                            # frame (0 = forward)
        )
        
        # Add distance array (72 distances, 2 bytes each)
        for i in range(72):
            if i < len(distances) and distances[i] is not None:
                distance_cm = min(distances[i], 65535)  # Cap at 65535 cm
            else:
                distance_cm = 65535  # No obstacle
            payload += struct.pack('<H', distance_cm)
        
        # Add remaining fields
        payload += struct.pack('<fHHfBB',
            5.0,      # increment (degrees)
            0,        # min_distance (cm)
            10000,    # max_distance (cm)
            5.0,      # increment_f (degrees)
            0,        # angle_offset
            0         # frame
        )
        
        header = self.create_mavlink_header(self.MAVLINK_MSG_ID_OBSTACLE_DISTANCE, len(payload))
        message = header + payload
        checksum = self.calculate_checksum(message)
        message += struct.pack('<H', checksum)
        
        self.send_message(message)
    
    def send_message(self, message: bytes):
        """Send MAVLink message via UDP"""
        if self.sock:
            try:
                self.sock.sendto(message, (self.host, self.port))
            except Exception as e:
                logger.error(f"Failed to send MAVLink message: {e}")
    
    def connect(self) -> bool:
        """Connect to MAVProxy UDP output"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            logger.info(f"Connected to MAVProxy at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MAVProxy: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MAVProxy"""
        if self.sock:
            self.sock.close()
            self.sock = None
            logger.info("Disconnected from MAVProxy")


class MR72MAVLinkBridge:
    """Bridge between MR72 radar and MAVLink"""
    
    def __init__(self, radar_port="/dev/ttyS0", mavlink_host="127.0.0.1", mavlink_port=14551):
        self.radar = MR72Radar(radar_port)
        self.mavlink = MAVLinkSender(mavlink_host, mavlink_port)
        self.running = False
        self.send_interval = 0.1  # Send data every 100ms
    
    def start(self):
        """Start the bridge"""
        if not self.radar.start():
            logger.error("Failed to start radar")
            return False
        
        if not self.mavlink.connect():
            logger.error("Failed to connect to MAVProxy")
            return False
        
        self.running = True
        self.bridge_thread = threading.Thread(target=self.bridge_loop, daemon=True)
        self.bridge_thread.start()
        logger.info("MR72-MAVLink bridge started")
        return True
    
    def stop(self):
        """Stop the bridge"""
        self.running = False
        self.radar.stop()
        self.mavlink.disconnect()
        logger.info("MR72-MAVLink bridge stopped")
    
    def bridge_loop(self):
        """Main bridge loop - reads radar data and sends MAVLink messages"""
        while self.running:
            try:
                # Get latest radar data
                radar_data = self.radar.get_latest_data()
                
                if radar_data:
                    # Send sector data as distance sensors
                    sector_orientations = {
                        'sector1': 0,    # Forward
                        'sector2': 45,   # 45 degrees right
                        'sector3': -45   # 45 degrees left
                    }
                    
                    for sector, orientation in sector_orientations.items():
                        if sector in radar_data and radar_data[sector] is not None:
                            # Convert mm to cm
                            distance_cm = radar_data[sector] // 10
                            self.mavlink.send_distance_sensor(distance_cm, 0, orientation)
                    
                    # Create obstacle distance array for 360-degree coverage
                    # Map radar sectors to 72-point array (5-degree increments)
                    obstacle_distances = [65535] * 72  # Initialize with no obstacle
                    
                    # Map sectors to angle ranges
                    sector_mappings = {
                        'sector1': (0, 56),      # 0-56 degrees
                        'sector2': (56, 112),    # 56-112 degrees  
                        'sector3': (112, 168),   # 112-168 degrees
                    }
                    
                    for sector, (start_angle, end_angle) in sector_mappings.items():
                        if sector in radar_data and radar_data[sector] is not None:
                            distance_cm = radar_data[sector] // 10
                            # Map to 5-degree increments
                            start_idx = int(start_angle / 5)
                            end_idx = int(end_angle / 5)
                            for i in range(start_idx, min(end_idx, 72)):
                                obstacle_distances[i] = distance_cm
                    
                    # Send obstacle distance message
                    self.mavlink.send_obstacle_distance(obstacle_distances)
                    
                    logger.debug(f"Sent radar data: {radar_data}")
                
                time.sleep(self.send_interval)
                
            except Exception as e:
                logger.error(f"Error in bridge loop: {e}")
                time.sleep(0.1)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MR72 Radar to MAVLink Bridge")
    parser.add_argument("--radar-port", default="/dev/ttyS0", help="MR72 radar serial port")
    parser.add_argument("--mavlink-host", default="127.0.0.1", help="MAVProxy UDP host")
    parser.add_argument("--mavlink-port", type=int, default=14551, help="MAVProxy UDP port")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start bridge
    bridge = MR72MAVLinkBridge(args.radar_port, args.mavlink_host, args.mavlink_port)
    
    try:
        if bridge.start():
            logger.info("Bridge running. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        else:
            logger.error("Failed to start bridge")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main() 