#!/bin/bash

# MR72 Radar Bridge Management Script

LOG_DIR="/var/log/usb_cam_radar"
PID_FILE_RADAR="$LOG_DIR/radar.pid"
PID_FILE_WEBCAM="$LOG_DIR/webcam.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if service is running
is_running() {
    local pid_file=$1
    local service_name=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            return 0
        else
            echo -e "${YELLOW}Warning: $service_name PID file exists but process is not running${NC}"
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# Function to start radar bridge
start_radar() {
    echo -e "${GREEN}Starting MR72 Radar Bridge...${NC}"
    
    if is_running "$PID_FILE_RADAR" "Radar Bridge"; then
        echo -e "${YELLOW}Radar bridge is already running${NC}"
        return 1
    fi
    
    # Create log directory
    mkdir -p $LOG_DIR
    
    # Start radar bridge
    python3 mr72_mavlink.py \
        --uart-port /dev/ttyS0 \
        --uart-baud 115200 \
        --mavlink-port /dev/ttyACM1 \
        --mavlink-baud 115200 \
        --verbose > "$LOG_DIR/radar_bridge.log" 2>&1 &
    
    local pid=$!
    echo $pid > "$PID_FILE_RADAR"
    
    sleep 2
    if is_running "$PID_FILE_RADAR" "Radar Bridge"; then
        echo -e "${GREEN}Radar bridge started successfully (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}Failed to start radar bridge${NC}"
        rm -f "$PID_FILE_RADAR"
        return 1
    fi
}

# Function to stop radar bridge
stop_radar() {
    echo -e "${YELLOW}Stopping MR72 Radar Bridge...${NC}"
    
    if [ -f "$PID_FILE_RADAR" ]; then
        local pid=$(cat "$PID_FILE_RADAR")
        if kill $pid 2>/dev/null; then
            echo -e "${GREEN}Radar bridge stopped (PID: $pid)${NC}"
        else
            echo -e "${YELLOW}Radar bridge was not running${NC}"
        fi
        rm -f "$PID_FILE_RADAR"
    else
        echo -e "${YELLOW}Radar bridge is not running${NC}"
    fi
}

# Function to start webcam server
start_webcam() {
    echo -e "${GREEN}Starting Webcam Server...${NC}"
    
    if is_running "$PID_FILE_WEBCAM" "Webcam Server"; then
        echo -e "${YELLOW}Webcam server is already running${NC}"
        return 1
    fi
    
    # Create log directory
    mkdir -p $LOG_DIR
    
    # Start webcam server
    python3 webcam.py --host 0.0.0.0 --port 8080 > "$LOG_DIR/webcam.log" 2>&1 &
    
    local pid=$!
    echo $pid > "$PID_FILE_WEBCAM"
    
    sleep 2
    if is_running "$PID_FILE_WEBCAM" "Webcam Server"; then
        echo -e "${GREEN}Webcam server started successfully (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}Failed to start webcam server${NC}"
        rm -f "$PID_FILE_WEBCAM"
        return 1
    fi
}

# Function to stop webcam server
stop_webcam() {
    echo -e "${YELLOW}Stopping Webcam Server...${NC}"
    
    if [ -f "$PID_FILE_WEBCAM" ]; then
        local pid=$(cat "$PID_FILE_WEBCAM")
        if kill $pid 2>/dev/null; then
            echo -e "${GREEN}Webcam server stopped (PID: $pid)${NC}"
        else
            echo -e "${YELLOW}Webcam server was not running${NC}"
        fi
        rm -f "$PID_FILE_WEBCAM"
    else
        echo -e "${YELLOW}Webcam server is not running${NC}"
    fi
}

# Function to start both services
start_all() {
    echo -e "${GREEN}Starting all services...${NC}"
    start_webcam
    sleep 2
    start_radar
}

# Function to stop both services
stop_all() {
    echo -e "${YELLOW}Stopping all services...${NC}"
    stop_radar
    stop_webcam
}

# Function to show status
status() {
    echo -e "${GREEN}=== Service Status ===${NC}"
    
    if is_running "$PID_FILE_WEBCAM" "Webcam Server"; then
        local webcam_pid=$(cat "$PID_FILE_WEBCAM")
        echo -e "${GREEN}✓ Webcam Server: Running (PID: $webcam_pid)${NC}"
    else
        echo -e "${RED}✗ Webcam Server: Not running${NC}"
    fi
    
    if is_running "$PID_FILE_RADAR" "Radar Bridge"; then
        local radar_pid=$(cat "$PID_FILE_RADAR")
        echo -e "${GREEN}✓ MR72 Radar Bridge: Running (PID: $radar_pid)${NC}"
    else
        echo -e "${RED}✗ MR72 Radar Bridge: Not running${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}=== Log Files ===${NC}"
    if [ -d "$LOG_DIR" ]; then
        ls -la "$LOG_DIR"
    else
        echo "No log directory found"
    fi
}

# Function to show logs
logs() {
    local service=$1
    
    case $service in
        "radar"|"r")
            if [ -f "$LOG_DIR/radar_bridge.log" ]; then
                tail -f "$LOG_DIR/radar_bridge.log"
            else
                echo -e "${RED}Radar bridge log file not found${NC}"
            fi
            ;;
        "webcam"|"w")
            if [ -f "$LOG_DIR/webcam.log" ]; then
                tail -f "$LOG_DIR/webcam.log"
            else
                echo -e "${RED}Webcam log file not found${NC}"
            fi
            ;;
        *)
            echo -e "${YELLOW}Usage: $0 logs [radar|webcam]${NC}"
            ;;
    esac
}

# Function to show help
show_help() {
    echo "MR72 Radar Bridge Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start-all     Start both webcam server and radar bridge"
    echo "  stop-all      Stop both services"
    echo "  start-radar   Start only the radar bridge"
    echo "  stop-radar    Stop only the radar bridge"
    echo "  start-webcam  Start only the webcam server"
    echo "  stop-webcam   Stop only the webcam server"
    echo "  status        Show status of all services"
    echo "  logs [radar|webcam]  Show live logs for specified service"
    echo "  restart       Restart all services"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start-all"
    echo "  $0 status"
    echo "  $0 logs radar"
}

# Main script logic
case "$1" in
    "start-all")
        start_all
        ;;
    "stop-all")
        stop_all
        ;;
    "start-radar")
        start_radar
        ;;
    "stop-radar")
        stop_radar
        ;;
    "start-webcam")
        start_webcam
        ;;
    "stop-webcam")
        stop_webcam
        ;;
    "status")
        status
        ;;
    "logs")
        logs $2
        ;;
    "restart")
        stop_all
        sleep 2
        start_all
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac 