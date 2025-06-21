# MR72 Radar to MAVLink Bridge

This system integrates the MR72 UART radar with a flight controller using MAVLink protocol for obstacle avoidance and proximity detection.

## Overview

The MR72 radar bridge reads distance data from the MR72 radar via UART (`/dev/ttyS0`) and sends it to the flight controller via MAVLink (`/dev/ttyACM1`). It provides:

- **Real-time distance data** from all radar sectors
- **MAVLink DISTANCE_SENSOR messages** for individual sectors (1, 2, 3)
- **MAVLink OBSTACLE_DISTANCE messages** for comprehensive 360° coverage
- **Automatic data conversion** from millimeters to centimeters
- **Robust error handling** and logging

## Hardware Setup

### Connections
- **MR72 Radar**: Connected to `/dev/ttyS0` (UART)
- **Flight Controller**: Connected to `/dev/ttyACM1` (SLCAN port)
- **USB Camera**: Connected to USB port for video streaming

### MR72 Protocol
The MR72 radar outputs data in the following format:
- **Baud Rate**: 115200
- **Data Bits**: 8
- **Stop Bits**: 1
- **Parity**: None
- **Frame Length**: 19 bytes
- **Update Rate**: ~16.67 Hz (60ms cycle)

### Frame Structure
```
Header: TH (0x54, 0x48) - 2 bytes
D1: Sector 2 (90°) - 2 bytes
D2: Sector 3 (180°) - 2 bytes  
D3: 90° sector - 2 bytes
D4: 135° sector - 2 bytes
D5: 180° sector - 2 bytes
D6: 225° sector - 2 bytes
D7: 270° sector - 2 bytes
D8: Sector 1 (0°) - 2 bytes
CRC8: 1 byte (skipped in this implementation)
```

## Installation

1. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Make scripts executable** (on Linux/Raspberry Pi):
   ```bash
   chmod +x start_radar_bridge.sh start_combined.sh manage_radar.sh
   ```

## Usage

### Quick Start

1. **Start both services** (webcam + radar):
   ```bash
   ./start_combined.sh
   ```

2. **Or start services individually**:
   ```bash
   # Start webcam server
   python3 webcam.py --host 0.0.0.0 --port 8080
   
   # Start radar bridge
   python3 mr72_mavlink.py --uart-port /dev/ttyS0 --mavlink-port /dev/ttyACM1
   ```

### Management Script

Use the management script for easy service control:

```bash
# Start all services
./manage_radar.sh start-all

# Check status
./manage_radar.sh status

# View logs
./manage_radar.sh logs radar
./manage_radar.sh logs webcam

# Stop all services
./manage_radar.sh stop-all

# Restart all services
./manage_radar.sh restart
```

### Command Line Options

```bash
python3 mr72_mavlink.py [OPTIONS]

Options:
  --uart-port PORT      UART port for MR72 radar (default: /dev/ttyS0)
  --uart-baud RATE      UART baud rate (default: 115200)
  --mavlink-port PORT   MAVLink port for flight controller (default: /dev/ttyACM1)
  --mavlink-baud RATE   MAVLink baud rate (default: 115200)
  --verbose, -v         Enable verbose logging
  --help                Show help message
```

## MAVLink Messages

### DISTANCE_SENSOR Messages
Individual distance sensor messages are sent for sectors 1, 2, and 3:

- **Sector 1 (0°)**: `MAV_SENSOR_ROTATION_NONE`
- **Sector 2 (90°)**: `MAV_SENSOR_ROTATION_90_DEG`
- **Sector 3 (180°)**: `MAV_SENSOR_ROTATION_180_DEG`

### OBSTACLE_DISTANCE Message
A comprehensive 72-element array covering 360° in 5° increments:

- **Valid sectors**: Real distance data from MR72
- **Other sectors**: Maximum distance (100m) for obstacle avoidance
- **Update rate**: 10 Hz
- **Distance range**: 10cm to 100m

## Testing

### Test Protocol Parser
```bash
python3 test_mr72_parser.py
```

This tests the MR72 protocol parsing with sample data without requiring hardware.

### Test UART Connection
```bash
# Check if UART port exists
ls -la /dev/ttyS0

# Test UART communication (if you have the hardware)
python3 mr72_raw.py
```

### Test MAVLink Connection
```bash
# Check if MAVLink port exists
ls -la /dev/ttyACM1

# Test with verbose logging
python3 mr72_mavlink.py --verbose
```

## Configuration

### Flight Controller Setup
Ensure your flight controller is configured to:
- Accept MAVLink messages on the SLCAN port
- Process `DISTANCE_SENSOR` and `OBSTACLE_DISTANCE` messages
- Enable obstacle avoidance features

### MAVProxy Configuration
If using MAVProxy, ensure it's configured to:
- Forward MAVLink messages between GCS and flight controller
- Allow additional MAVLink sources

## Troubleshooting

### Common Issues

1. **Import Error**: `cannot import name 'mavlink'`
   - **Solution**: The import structure has been fixed in the current version

2. **UART Permission Denied**
   - **Solution**: Add user to dialout group: `sudo usermod -a -G dialout $USER`

3. **MAVLink Connection Failed**
   - **Solution**: Check if flight controller is connected and SLCAN is enabled

4. **No Radar Data**
   - **Solution**: Verify MR72 radar is powered and connected to correct UART port

### Log Files
Logs are stored in `/var/log/usb_cam_radar/`:
- `radar_bridge.log`: MR72 radar bridge logs
- `webcam.log`: Webcam server logs
- `radar.pid`: Radar bridge process ID
- `webcam.pid`: Webcam server process ID

### Debug Mode
Enable verbose logging for detailed debugging:
```bash
python3 mr72_mavlink.py --verbose
```

## Integration with Existing System

The MR72 radar bridge is designed to work alongside the existing webcam server:

- **Webcam Server**: Handles video streaming via WebRTC
- **Radar Bridge**: Handles obstacle detection via MAVLink
- **Combined Script**: Runs both services together

Both services can run independently or together using the management scripts.

## Performance

- **UART Reading**: Continuous at ~16.67 Hz (MR72 update rate)
- **MAVLink Sending**: 10 Hz update rate
- **Memory Usage**: Minimal (< 10MB)
- **CPU Usage**: Low (< 5% on Raspberry Pi 4)

## Safety Features

- **Invalid Distance Handling**: Properly handles 0xFFFF invalid distances
- **Connection Monitoring**: Automatic reconnection attempts
- **Error Logging**: Comprehensive error reporting
- **Graceful Shutdown**: Proper cleanup on exit

## Future Enhancements

- **CRC8 Validation**: Add proper CRC8 checking (currently skipped)
- **Configuration File**: Support for configuration files
- **Web Interface**: Add web-based monitoring and control
- **Data Logging**: Save radar data to files for analysis
- **Multiple Radars**: Support for multiple MR72 units

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review log files in `/var/log/usb_cam_radar/`
3. Test with `test_mr72_parser.py` to verify protocol parsing
4. Enable verbose logging for detailed debugging 