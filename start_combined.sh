#!/bin/bash

# Combined Startup Script
# Runs both webcam server and MR72 radar bridge

echo "Starting Combined USB Camera and MR72 Radar System..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

# Check if required packages are installed
echo "Checking dependencies..."
python3 -c "import pymavlink, serial, aiohttp, aiortc" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required packages..."
    pip3 install -r requirements.txt
fi

# Set up logging directory
LOG_DIR="/var/log/usb_cam_radar"
mkdir -p $LOG_DIR

# Function to handle cleanup on exit
cleanup() {
    echo "Shutting down services..."
    if [ ! -z "$WEBCAM_PID" ]; then
        kill $WEBCAM_PID 2>/dev/null
    fi
    if [ ! -z "$RADAR_PID" ]; then
        kill $RADAR_PID 2>/dev/null
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start webcam server in background
echo "Starting webcam server..."
python3 webcam.py --host 0.0.0.0 --port 8080 &
WEBCAM_PID=$!
echo "Webcam server started with PID: $WEBCAM_PID"

# Wait a moment for webcam to initialize
sleep 2

# Start MR72 radar bridge in background
echo "Starting MR72 radar bridge..."
python3 mr72_mavlink.py \
    --uart-port /dev/ttyS0 \
    --uart-baud 115200 \
    --mavlink-port /dev/ttyACM1 \
    --mavlink-baud 115200 \
    --verbose &
RADAR_PID=$!
echo "MR72 radar bridge started with PID: $RADAR_PID"

# Log PIDs for management
echo $WEBCAM_PID > $LOG_DIR/webcam.pid
echo $RADAR_PID > $LOG_DIR/radar.pid

echo "All services started successfully!"
echo "Webcam server PID: $WEBCAM_PID"
echo "Radar bridge PID: $RADAR_PID"
echo "Logs available in: $LOG_DIR"
echo "Press Ctrl+C to stop all services"

# Wait for either process to exit
wait 