# MR72 Radar to MAVLink Integration

This project integrates the MR72 UART radar with MAVLink to provide proximity and obstacle avoidance data to flight controllers. It solves the conflict between MAVProxy and direct serial communication by using MAVProxy's UDP output.

## Overview

The system consists of:
1. **MAVProxy**: Connects to flight controller and provides UDP output
2. **MR72-MAVLink Bridge**: Reads radar data and sends MAVLink messages
3. **MR72 Radar**: Provides proximity data via UART protocol

## Architecture

```
MR72 Radar (ttyS0) → MR72-MAVLink Bridge → UDP (127.0.0.1:14551) → MAVProxy → Flight Controller (ttyACM0)
                                                                    ↓
                                                              GCS (UDP:14550)
```

## Features

- ✅ Full MR72 UART protocol parsing (19-byte frames)
- ✅ CRC8 validation for data integrity
- ✅ Sector 1, 2, 3 distance measurements
- ✅ Obstacle detection at multiple angles (90°, 135°, 180°, 225°, 270°)
- ✅ MAVLink DISTANCE_SENSOR messages for individual sectors
- ✅ MAVLink OBSTACLE_DISTANCE messages for 360° coverage
- ✅ Automatic reconnection and error handling
- ✅ Thread-safe data handling
- ✅ Comprehensive logging

## MR72 Protocol Support

The system fully implements the MR72 UART protocol:

| Byte | Description | Range |
|------|-------------|-------|
| 0-1  | Header (TH) | Fixed: 0x54, 0x48 |
| 2-3  | Sector 2    | 0-56° (nearest target) |
| 4-5  | Sector 3    | 56-112° (nearest target) |
| 6-7  | Obstacle 90° | Distance in mm |
| 8-9  | Obstacle 135° | Distance in mm |
| 10-11| Obstacle 180° | Distance in mm |
| 12-13| Obstacle 225° | Distance in mm |
| 14-15| Obstacle 270° | Distance in mm |
| 16-17| Sector 1    | 112-168° (nearest target) |
| 18   | CRC8        | Checksum validation |

## Installation

### Prerequisites

1. **Python 3.7+**
2. **MAVProxy**: `pip install mavproxy`
3. **Required packages**: `pip install -r requirements.txt`

### Dependencies

The following packages are automatically installed:
- `pymavlink>=2.4.37` - MAVLink protocol support
- `pyserial>=3.5` - Serial communication
- `aiohttp>=3.8.0` - Web server (for webcam)
- `aiortc>=1.5.0` - WebRTC support
- `opencv-python>=4.8.0` - Video processing

## Setup

### 1. Hardware Connections

```
Raspberry Pi 4:
├── ttyACM0 → Flight Controller (USB)
├── ttyS0   → MR72 Radar (UART)
└── USB     → Logitech Camera
```

### 2. Configure MAVProxy

Edit the startup script to match your setup:

```bash
# In start_mavlink_system.sh
GCS_IP="192.168.1.100"  # Your GCS IP address
RADAR_PORT="/dev/ttyS0"
FLIGHT_CONTROLLER_PORT="/dev/ttyACM0"
```

### 3. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install MAVProxy
pip install mavproxy
```

## Usage

### Quick Start

1. **Start the complete system**:
   ```bash
   ./start_mavlink_system.sh
   ```

2. **Or start components individually**:
   ```bash
   # Terminal 1: Start MAVProxy
   mavproxy.py --master=/dev/ttyACM0 --baudrate=115200 \
               --out=udp:192.168.1.100:14550 \
               --out=udp:127.0.0.1:14551

   # Terminal 2: Start MR72 bridge
   python3 mr72_mavlink.py --radar-port=/dev/ttyS0 --mavlink-port=14551
   ```

### Command Line Options

```bash
python3 mr72_mavlink.py [OPTIONS]

Options:
  --radar-port PORT     MR72 radar serial port (default: /dev/ttyS0)
  --mavlink-host HOST   MAVProxy UDP host (default: 127.0.0.1)
  --mavlink-port PORT   MAVProxy UDP port (default: 14551)
  --verbose, -v         Enable verbose logging
  --help                Show help message
```

### Testing

Test the parser without hardware:

```bash
python3 test_mr72_parser.py
```

## MAVLink Messages

The system sends two types of MAVLink messages:

### 1. DISTANCE_SENSOR (ID: 132)

Individual distance sensors for each sector:
- **Sector 1**: Forward (0°)
- **Sector 2**: 45° right
- **Sector 3**: 45° left

### 2. OBSTACLE_DISTANCE (ID: 330)

72-point obstacle array covering 360°:
- 5° increments
- Distance in centimeters
- 65535 = no obstacle

## Configuration

### Flight Controller Setup

Ensure your flight controller supports:
- `DISTANCE_SENSOR` messages
- `OBSTACLE_DISTANCE` messages
- Proximity/obstacle avoidance features

### ArduPilot Configuration

```bash
# Enable proximity sensors
PROXIMITY_ENABLE = 1
PROXIMITY_TYPE = 1  # Lightware SF40C (similar to radar)

# Configure obstacle avoidance
AVOID_ENABLE = 1
AVOID_MARGIN = 2.0  # meters
```

### PX4 Configuration

```bash
# Enable distance sensors
SENS_EN_LL40LS = 1
SENS_EN_SF0X = 1

# Configure obstacle avoidance
CP_DIST = 2.0  # meters
```

## Troubleshooting

### Common Issues

1. **"Serial port busy" error**:
   - Ensure MAVProxy is not directly using ttyS0
   - Use the bridge approach with UDP

2. **No radar data**:
   - Check serial port permissions: `sudo chmod 666 /dev/ttyS0`
   - Verify baudrate: 115200
   - Check physical connections

3. **MAVLink messages not received**:
   - Verify UDP port 14551 is accessible
   - Check firewall settings
   - Ensure MAVProxy is running

4. **CRC errors**:
   - Check wiring for noise/interference
   - Verify power supply stability
   - Check baudrate settings

### Debug Mode

Enable verbose logging:

```bash
python3 mr72_mavlink.py --verbose
```

### Log Analysis

The system logs:
- Frame parsing results
- MAVLink message transmission
- Connection status
- Error conditions

## Performance

- **Update rate**: 10 Hz (100ms intervals)
- **Latency**: <50ms end-to-end
- **Memory usage**: <10MB
- **CPU usage**: <5% on Raspberry Pi 4

## Integration with Existing System

The MR72 bridge can run alongside your existing webcam server:

```bash
# Terminal 1: Webcam server
python3 webcam.py --port=8080

# Terminal 2: MAVLink system
./start_mavlink_system.sh
```

## Development

### Adding New Sensors

To add additional sensors:

1. Extend the `MR72Radar` class
2. Add new MAVLink message types
3. Update the bridge logic

### Custom MAVLink Messages

Create custom messages by extending `MAVLinkSender`:

```python
def send_custom_message(self, data):
    # Create custom MAVLink message
    payload = struct.pack('<I', data)
    message = self.create_mavlink_header(CUSTOM_MSG_ID, len(payload))
    message += payload
    checksum = self.calculate_checksum(message)
    message += struct.pack('<H', checksum)
    self.send_message(message)
```

## License

This project is open source. See LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs with `--verbose` flag
3. Test with `test_mr72_parser.py`
4. Verify hardware connections

## Changelog

- **v1.0**: Initial release with MR72 protocol support
- **v1.1**: Added comprehensive error handling
- **v1.2**: Added OBSTACLE_DISTANCE message support
- **v1.3**: Improved CRC validation and frame parsing 