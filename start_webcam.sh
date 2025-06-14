#!/bin/bash

# Wait for network connectivity
while ! ping -c 1 -W 1 8.8.8.8; do
    sleep 1
done

# Activate virtual environment
source "$(dirname "$0")/venv/bin/activate"

# Create a new tmux session named 'webcam' if it doesn't exist
tmux new-session -d -s webcam

# Send the command to start the webcam server
tmux send-keys -t webcam "python3 $(dirname "$0")/webcam.py" C-m

# Keep the script running
while true; do
    sleep 3600
done 