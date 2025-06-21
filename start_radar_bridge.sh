#!/bin/bash

# MR72 Radar Bridge Startup Script
# This script starts the MR72 radar to MAVLink bridge

echo "Starting MR72 Radar Bridge..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

# Check if required packages are installed
echo "Checking dependencies..."
python3 -c "import pymavlink, serial" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required packages..."
    pip3 install pymavlink pyserial
fi

# Check if UART port exists
if [ ! -e "/dev/ttyS0" ]; then
    echo "Warning: /dev/ttyS0 not found. Make sure MR72 radar is connected."
fi

# Check if MAVLink port exists
if [ ! -e "/dev/ttyACM1" ]; then
    echo "Warning: /dev/ttyACM1 not found. Make sure flight controller is connected."
fi

# Set up logging directory
LOG_DIR="/var/log/mr72_radar"
mkdir -p $LOG_DIR

# Start the radar bridge
echo "Starting MR72 radar bridge..."
python3 mr72_mavlink.py \
    --uart-port /dev/ttyS0 \
    --uart-baud 115200 \
    --mavlink-port /dev/ttyACM1 \
    --mavlink-baud 115200 \
    --verbose \
    2>&1 | tee $LOG_DIR/radar_bridge.log

echo "MR72 Radar Bridge stopped." 