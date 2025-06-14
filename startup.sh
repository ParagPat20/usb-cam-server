#!/bin/bash

# Function to create webcam tmux session
create_webcam_session() {
    if ! tmux has-session -t webcam 2>/dev/null; then
        tmux new-session -d -s webcam
        tmux send-keys -t webcam "cd $(pwd) && source venv/bin/activate && python webcam.py" C-m
        echo "Webcam tmux session created"
    else
        echo "Webcam tmux session already exists"
    fi
}

# Function to create tunnel tmux session
create_tunnel_session() {
    if ! tmux has-session -t tunnel 2>/dev/null; then
        tmux new-session -d -s tunnel
        tmux send-keys -t tunnel "cd $(pwd) && ./tunnel.sh" C-m
        echo "Tunnel tmux session created"
    else
        echo "Tunnel tmux session already exists"
    fi
}

# Create both sessions
create_webcam_session
create_tunnel_session

echo "Both tmux sessions have been created"
echo "To view webcam session: tmux attach -t webcam"
echo "To view tunnel session: tmux attach -t tunnel"
echo "To detach from a session: Press Ctrl+B then D" 