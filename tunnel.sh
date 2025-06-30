#!/bin/bash

# Configuration
EC2_USER="ubuntu"
EC2_HOST="3.7.55.44"
EC2_KEY_PATH="Jecon.pem"
LOCAL_PORT=8080
REMOTE_PORT=8080
RETRY_DELAY=5  # seconds to wait before retrying

# Function to log messages with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if tunnel is working
check_tunnel() {
    # Try to connect to the remote port to verify tunnel is working
    timeout 5 bash -c "</dev/tcp/$EC2_HOST/$REMOTE_PORT" 2>/dev/null
    return $?
}

# Ensure the key file has correct permissions
chmod 400 $EC2_KEY_PATH

log_message "Starting SSH tunnel with auto-restart capability"
log_message "Local port: $LOCAL_PORT, Remote port: $REMOTE_PORT"
log_message "Remote host: $EC2_USER@$EC2_HOST"

# Main loop to keep tunnel running
while true; do
    log_message "Attempting to establish SSH tunnel..."
    
    # Create the SSH tunnel with -g flag to allow remote hosts to connect
    ssh -N -g -R 0.0.0.0:$REMOTE_PORT:localhost:$LOCAL_PORT -i $EC2_KEY_PATH $EC2_USER@$EC2_HOST
    
    # Check if SSH command failed
    if [ $? -ne 0 ]; then
        log_message "SSH tunnel failed or was interrupted"
    else
        log_message "SSH tunnel exited normally"
    fi
    
    log_message "Waiting $RETRY_DELAY seconds before retrying..."
    sleep $RETRY_DELAY
    
    log_message "Restarting tunnel..."
done 