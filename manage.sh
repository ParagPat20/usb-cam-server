#!/bin/bash

# Function to check if virtual environment exists
check_venv() {
    if [ ! -d "venv" ]; then
        echo "Virtual environment not found. Setting up..."
        chmod +x setup_venv.sh
        ./setup_venv.sh
    fi
}

# Function to start webcam in tmux
start_webcam_tmux() {
    if ! tmux has-session -t webcam 2>/dev/null; then
        tmux new-session -d -s webcam
        tmux send-keys -t webcam "cd $(pwd) && source venv/bin/activate && python webcam.py" C-m
        echo "Webcam started in tmux session 'webcam'"
    else
        echo "Webcam tmux session already exists"
    fi
}

# Function to stop webcam tmux
stop_webcam_tmux() {
    if tmux has-session -t webcam 2>/dev/null; then
        tmux kill-session -t webcam
        echo "Webcam tmux session stopped"
    else
        echo "No webcam tmux session found"
    fi
}

# Function to view webcam logs
view_webcam_tmux() {
    if tmux has-session -t webcam 2>/dev/null; then
        tmux attach-session -t webcam
    else
        echo "No webcam tmux session found"
    fi
}

# Function to start tunnel in tmux
start_tunnel_tmux() {
    if ! tmux has-session -t tunnel 2>/dev/null; then
        tmux new-session -d -s tunnel
        tmux send-keys -t tunnel "cd $(pwd) && ./tunnel.sh" C-m
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

# Function to view tunnel logs
view_tunnel_tmux() {
    if tmux has-session -t tunnel 2>/dev/null; then
        tmux attach-session -t tunnel
    else
        echo "No tunnel tmux session found"
    fi
}

# Function to start all in tmux
start_all_tmux() {
    start_webcam_tmux
    start_tunnel_tmux
    echo "All services started in tmux"
}

# Function to stop all tmux sessions
stop_all_tmux() {
    stop_webcam_tmux
    stop_tunnel_tmux
    echo "All tmux sessions stopped"
}

# Function to view all tmux sessions
list_tmux() {
    echo "=== Active Tmux Sessions ==="
    tmux ls
}

# Function to install startup service
install_startup() {
    sudo cp startup.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable startup.service
    echo "Startup service installed and enabled"
}

# Main script
case "$1" in
    "start-webcam")
        start_webcam_tmux
        ;;
    "stop-webcam")
        stop_webcam_tmux
        ;;
    "view-webcam")
        view_webcam_tmux
        ;;
    "start-tunnel")
        start_tunnel_tmux
        ;;
    "stop-tunnel")
        stop_tunnel_tmux
        ;;
    "view-tunnel")
        view_tunnel_tmux
        ;;
    "start-all")
        start_all_tmux
        ;;
    "stop-all")
        stop_all_tmux
        ;;
    "list")
        list_tmux
        ;;
    "install-startup")
        install_startup
        ;;
    "setup")
        check_venv
        ;;
    *)
        echo "Usage: $0 {start-webcam|stop-webcam|view-webcam|start-tunnel|stop-tunnel|view-tunnel|start-all|stop-all|list|install-startup|setup}"
        exit 1
        ;;
esac 