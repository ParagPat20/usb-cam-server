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

# Function to setup terminal
setup_terminal() {
    chmod +x setup_terminal.sh
    ./setup_terminal.sh
}

# Function to start tunnel
start_tunnel() {
    chmod +x tunnel.sh
    ./tunnel.sh
}

# Function to stop tunnel
stop_tunnel() {
    pkill -f "ssh -N"
    echo "Tunnel stopped"
}

# Function to check tunnel status
status_tunnel() {
    if pgrep -f "ssh -N" > /dev/null; then
        echo "Tunnel is running"
        ps aux | grep "ssh -N" | grep -v grep
    else
        echo "Tunnel is not running"
    fi
}

# Function to start tunnel in tmux
start_tunnel_tmux() {
    if ! tmux has-session -t tunnel 2>/dev/null; then
        tmux new-session -d -s tunnel
        tmux send-keys -t tunnel "chmod +x tunnel.sh && ./tunnel.sh" C-m
        echo "Tunnel started in tmux session 'tunnel'"
    else
        echo "Tunnel tmux session already exists"
    fi
}

# Function to stop tunnel in tmux
stop_tunnel_tmux() {
    if tmux has-session -t tunnel 2>/dev/null; then
        tmux kill-session -t tunnel
        echo "Tunnel tmux session stopped"
    else
        echo "No tunnel tmux session found"
    fi
}

# Function to view tunnel logs in tmux
view_tunnel_tmux() {
    if tmux has-session -t tunnel 2>/dev/null; then
        tmux attach-session -t tunnel
    else
        echo "No tunnel tmux session found"
    fi
}

# Function to install all services
install_all_services() {
    chmod +x install_services.sh
    sudo ./install_services.sh
}

# Function to start all services
start_all() {
    sudo systemctl start webcam.service
    sudo systemctl start tunnel.service
    echo "All services started"
}

# Function to stop all services
stop_all() {
    sudo systemctl stop webcam.service
    sudo systemctl stop tunnel.service
    echo "All services stopped"
}

# Function to restart all services
restart_all() {
    sudo systemctl restart webcam.service
    sudo systemctl restart tunnel.service
    echo "All services restarted"
}

# Function to check all services status
status_all() {
    echo "=== Webcam Service Status ==="
    sudo systemctl status webcam.service
    echo -e "\n=== Tunnel Service Status ==="
    sudo systemctl status tunnel.service
}

# Function to view all logs
logs_all() {
    sudo journalctl -u webcam.service -u tunnel.service -f
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
    "terminal")
        setup_terminal
        ;;
    "tunnel")
        start_tunnel
        ;;
    "tunnel-stop")
        stop_tunnel
        ;;
    "tunnel-status")
        status_tunnel
        ;;
    "tunnel-tmux")
        start_tunnel_tmux
        ;;
    "tunnel-tmux-stop")
        stop_tunnel_tmux
        ;;
    "tunnel-tmux-view")
        view_tunnel_tmux
        ;;
    "install-all")
        install_all_services
        ;;
    "start-all")
        start_all
        ;;
    "stop-all")
        stop_all
        ;;
    "restart-all")
        restart_all
        ;;
    "status-all")
        status_all
        ;;
    "logs-all")
        logs_all
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|setup|terminal|tunnel|tunnel-stop|tunnel-status|tunnel-tmux|tunnel-tmux-stop|tunnel-tmux-view|install-all|start-all|stop-all|restart-all|status-all|logs-all}"
        exit 1
        ;;
esac 