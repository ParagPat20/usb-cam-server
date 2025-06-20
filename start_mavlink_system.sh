#!/bin/bash

# MR72 Radar + MAVProxy Startup Script
# This script starts both MAVProxy and the MR72-MAVLink bridge

set -e

# Configuration
GCS_IP="192.168.1.100"  # Change this to your GCS IP address
MAVPROXY_PORT=14550
BRIDGE_PORT=14551
RADAR_PORT="/dev/ttyS0"
FLIGHT_CONTROLLER_PORT="/dev/ttyACM0"
BAUDRATE=115200

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a port is in use
port_in_use() {
    netstat -tuln 2>/dev/null | grep -q ":$1 "
}

# Function to check if a device exists
device_exists() {
    [ -e "$1" ]
}

# Function to kill processes by name
kill_process() {
    local process_name="$1"
    pkill -f "$process_name" 2>/dev/null || true
}

# Function to cleanup on exit
cleanup() {
    print_status "Cleaning up..."
    kill_process "mavproxy.py"
    kill_process "mr72_mavlink.py"
    print_success "Cleanup complete"
}

# Set up signal handlers
trap cleanup EXIT INT TERM

# Check prerequisites
print_status "Checking prerequisites..."

# Check if mavproxy is installed
if ! command_exists mavproxy.py; then
    print_error "MAVProxy not found. Please install MAVProxy first."
    print_status "Install with: pip install mavproxy"
    exit 1
fi

# Check if Python dependencies are installed
if ! python3 -c "import pymavlink, serial" 2>/dev/null; then
    print_error "Required Python packages not found."
    print_status "Install with: pip install -r requirements.txt"
    exit 1
fi

# Check if flight controller device exists
if ! device_exists "$FLIGHT_CONTROLLER_PORT"; then
    print_warning "Flight controller device $FLIGHT_CONTROLLER_PORT not found"
    print_status "Make sure your flight controller is connected"
fi

# Check if radar device exists
if ! device_exists "$RADAR_PORT"; then
    print_warning "Radar device $RADAR_PORT not found"
    print_status "Make sure your MR72 radar is connected"
fi

# Check if ports are available
if port_in_use $MAVPROXY_PORT; then
    print_warning "Port $MAVPROXY_PORT is already in use"
fi

if port_in_use $BRIDGE_PORT; then
    print_warning "Port $BRIDGE_PORT is already in use"
fi

print_success "Prerequisites check complete"

# Kill any existing processes
print_status "Stopping any existing processes..."
kill_process "mavproxy.py"
kill_process "mr72_mavlink.py"
sleep 2

# Start MAVProxy
print_status "Starting MAVProxy..."
print_status "MAVProxy command: mavproxy.py --master=$FLIGHT_CONTROLLER_PORT --baudrate=$BAUDRATE --out=udp:$GCS_IP:$MAVPROXY_PORT --out=udp:127.0.0.1:$BRIDGE_PORT"

mavproxy.py --master="$FLIGHT_CONTROLLER_PORT" --baudrate=$BAUDRATE \
            --out=udp:$GCS_IP:$MAVPROXY_PORT \
            --out=udp:127.0.0.1:$BRIDGE_PORT &
MAVPROXY_PID=$!

# Wait for MAVProxy to start
sleep 3

# Check if MAVProxy is running
if ! kill -0 $MAVPROXY_PID 2>/dev/null; then
    print_error "MAVProxy failed to start"
    exit 1
fi

print_success "MAVProxy started with PID $MAVPROXY_PID"

# Start MR72-MAVLink bridge
print_status "Starting MR72-MAVLink bridge..."
print_status "Bridge command: python3 mr72_mavlink.py --radar-port=$RADAR_PORT --mavlink-port=$BRIDGE_PORT"

python3 mr72_mavlink.py --radar-port="$RADAR_PORT" --mavlink-port=$BRIDGE_PORT &
BRIDGE_PID=$!

# Wait for bridge to start
sleep 2

# Check if bridge is running
if ! kill -0 $BRIDGE_PID 2>/dev/null; then
    print_error "MR72-MAVLink bridge failed to start"
    kill $MAVPROXY_PID 2>/dev/null || true
    exit 1
fi

print_success "MR72-MAVLink bridge started with PID $BRIDGE_PID"

# Display status
echo ""
print_success "System started successfully!"
print_status "MAVProxy PID: $MAVPROXY_PID"
print_status "Bridge PID: $BRIDGE_PID"
print_status "GCS connection: udp://$GCS_IP:$MAVPROXY_PORT"
print_status "Bridge connection: udp://127.0.0.1:$BRIDGE_PORT"
print_status "Radar port: $RADAR_PORT"
print_status "Flight controller port: $FLIGHT_CONTROLLER_PORT"
echo ""
print_status "Press Ctrl+C to stop all services"

# Wait for user interrupt
wait 