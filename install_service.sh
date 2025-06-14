#!/bin/bash

# Make the start script executable
chmod +x start_webcam.sh

# Copy the service file to systemd directory
sudo cp webcam.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable webcam.service

# Start the service
sudo systemctl start webcam.service

echo "Webcam service has been installed and started!"
echo "You can check the status with: sudo systemctl status webcam.service"
echo "To view logs: sudo journalctl -u webcam.service -f" 