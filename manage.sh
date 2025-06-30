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
        tmux send-keys -t tunnel "cd $(pwd) && chmod +x tunnel.sh && ./tunnel.sh" C-m
        echo "Tunnel started in tmux session 'tunnel' with auto-restart capability"
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

# Function to check tunnel status
check_tunnel_status() {
    if tmux has-session -t tunnel 2>/dev/null; then
        # Check if the tunnel process is still running
        if tmux list-panes -t tunnel -F "#{pane_pid}" | xargs ps -p >/dev/null 2>&1; then
            echo "Tunnel is running"
            return 0
        else
            echo "Tunnel session exists but process is not running"
            return 1
        fi
    else
        echo "No tunnel session found"
        return 1
    fi
}

# Function to restart tunnel if needed
restart_tunnel_if_needed() {
    if ! check_tunnel_status >/dev/null 2>&1; then
        echo "Tunnel is not running properly, restarting..."
        stop_tunnel_tmux
        sleep 2
        start_tunnel_tmux
        echo "Tunnel restarted"
    else
        echo "Tunnel is running properly"
    fi
}

# Function to diagnose tunnel issues
diagnose_tunnel() {
    echo "=== Tunnel Diagnosis ==="
    
    # Check if tmux session exists
    if tmux has-session -t tunnel 2>/dev/null; then
        echo "✓ Tunnel tmux session exists"
        
        # Check if process is running
        if tmux list-panes -t tunnel -F "#{pane_pid}" | xargs ps -p >/dev/null 2>&1; then
            echo "✓ Tunnel process is running"
            
            # Show recent logs
            echo "Recent tunnel logs:"
            tmux capture-pane -t tunnel -p | tail -10
        else
            echo "✗ Tunnel session exists but process is not running"
        fi
    else
        echo "✗ No tunnel tmux session found"
    fi
    
    # Check SSH key permissions
    if [ -f "Jecon.pem" ]; then
        perms=$(stat -c "%a" Jecon.pem 2>/dev/null || stat -f "%Lp" Jecon.pem 2>/dev/null)
        if [ "$perms" = "400" ]; then
            echo "✓ SSH key has correct permissions (400)"
        else
            echo "✗ SSH key has incorrect permissions ($perms), should be 400"
            echo "  Run: chmod 400 Jecon.pem"
        fi
    else
        echo "✗ SSH key file (Jecon.pem) not found"
    fi
    
    # Test SSH connectivity
    echo "Testing SSH connectivity..."
    if ssh -o ConnectTimeout=10 -o BatchMode=yes -i Jecon.pem ubuntu@3.7.55.44 "echo 'SSH connection successful'" 2>/dev/null; then
        echo "✓ SSH connection to remote host successful"
    else
        echo "✗ SSH connection to remote host failed"
        echo "  Check your internet connection and SSH key"
    fi
    
    # Check if remote port is in use
    echo "Checking remote port 8080..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes -i Jecon.pem ubuntu@3.7.55.44 "netstat -tln | grep :8080" >/dev/null 2>&1; then
        echo "✗ Remote port 8080 is already in use"
        echo "  This is likely causing the 'remote port forwarding failed' error"
        echo "  The tunnel script will try alternative ports automatically"
    else
        echo "✓ Remote port 8080 appears to be available"
    fi
}

# Function to start MR72 MAVLink in tmux
start_mr72_tmux() {
    if ! tmux has-session -t mr72 2>/dev/null; then
        tmux new-session -d -s mr72
        tmux send-keys -t mr72 "cd $(pwd) && source venv/bin/activate && python mr72_mavlink.py" C-m
        echo "MR72 MAVLink started in tmux session 'mr72'"
    else
        echo "MR72 MAVLink tmux session already exists"
    fi
}

# Function to stop MR72 MAVLink tmux
stop_mr72_tmux() {
    if tmux has-session -t mr72 2>/dev/null; then
        tmux kill-session -t mr72
        echo "MR72 MAVLink tmux session stopped"
    else
        echo "No MR72 MAVLink tmux session found"
    fi
}

# Function to view MR72 MAVLink logs
view_mr72_tmux() {
    if tmux has-session -t mr72 2>/dev/null; then
        tmux attach-session -t mr72
    else
        echo "No MR72 MAVLink tmux session found"
    fi
}

# Function to start all in tmux
start_all_tmux() {
    start_webcam_tmux
    start_tunnel_tmux
    start_mr72_tmux
    echo "All services started in tmux"
}

# Function to stop all tmux sessions
stop_all_tmux() {
    stop_webcam_tmux
    stop_tunnel_tmux
    stop_mr72_tmux
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
    "check-tunnel")
        check_tunnel_status
        ;;
    "restart-tunnel")
        restart_tunnel_if_needed
        ;;
    "start-mr72")
        start_mr72_tmux
        ;;
    "stop-mr72")
        stop_mr72_tmux
        ;;
    "view-mr72")
        view_mr72_tmux
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
    "diagnose-tunnel")
        diagnose_tunnel
        ;;
    *)
        echo "Usage: $0 {start-webcam|stop-webcam|view-webcam|start-tunnel|stop-tunnel|view-tunnel|check-tunnel|restart-tunnel|start-mr72|stop-mr72|view-mr72|start-all|stop-all|list|install-startup|setup|diagnose-tunnel}"
        exit 1
        ;;
esac 