#!/bin/bash

# Get the absolute path of the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Ensure all scripts are executable
chmod +x *.sh

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Function to create webcam tmux session
create_webcam_session() {
    if ! tmux has-session -t webcam 2>/dev/null; then
        tmux new-session -d -s webcam
        tmux send-keys -t webcam "cd $SCRIPT_DIR && source $SCRIPT_DIR/venv/bin/activate && python webcam.py" C-m
        echo "Webcam tmux session created"
    else
        echo "Webcam tmux session already exists"
    fi
}

# Function to create tunnel tmux session
create_tunnel_session() {
    if ! tmux has-session -t tunnel 2>/dev/null; then
        tmux new-session -d -s tunnel
        tmux send-keys -t tunnel "cd $SCRIPT_DIR && source $SCRIPT_DIR/venv/bin/activate && ./tunnel.sh" C-m
        echo "Tunnel tmux session created"
    else
        echo "Tunnel tmux session already exists"
    fi
}

# Wait for network
echo "Waiting for network..."
while ! ping -c 1 -W 1 8.8.8.8; do
    sleep 1
done
echo "Network is up"

# Create both sessions
create_webcam_session
sleep 5  # Wait for webcam to initialize
create_tunnel_session

echo "Both tmux sessions have been created"
echo "To view webcam session: tmux attach -t webcam"
echo "To view tunnel session: tmux attach -t tunnel"
echo "To detach from a session: Press Ctrl+B then D" 