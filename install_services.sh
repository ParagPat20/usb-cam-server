#!/bin/bash

# Get the absolute path of the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Copy service files to systemd directory
sudo cp "$SCRIPT_DIR/webcam.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/tunnel.service" /etc/systemd/system/

# Reload systemd to recognize new services
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable webcam.service
sudo systemctl enable tunnel.service

# Start services
sudo systemctl start webcam.service
sudo systemctl start tunnel.service

echo "Services installed and started successfully!"
echo "Check status with: sudo systemctl status webcam.service tunnel.service" 