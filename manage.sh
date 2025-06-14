#!/bin/bash

# Function to check if virtual environment exists
check_venv() {
    if [ ! -d "venv" ]; then
        echo "Virtual environment not found. Setting up..."
        chmod +x setup_venv.sh
        ./setup_venv.sh
    fi
}

# Function to start the service
start_service() {
    check_venv
    chmod +x install_service.sh
    sudo ./install_service.sh
}

# Function to stop the service
stop_service() {
    sudo systemctl stop webcam.service
    echo "Service stopped"
}

# Function to restart the service
restart_service() {
    sudo systemctl restart webcam.service
    echo "Service restarted"
}

# Function to check service status
status_service() {
    sudo systemctl status webcam.service
}

# Function to view logs
view_logs() {
    sudo journalctl -u webcam.service -f
}

# Main script
case "$1" in
    "start")
        start_service
        ;;
    "stop")
        stop_service
        ;;
    "restart")
        restart_service
        ;;
    "status")
        status_service
        ;;
    "logs")
        view_logs
        ;;
    "setup")
        check_venv
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|setup}"
        exit 1
        ;;
esac 