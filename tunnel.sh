#!/bin/bash

# Configuration
EC2_USER="ubuntu"
EC2_HOST="3.7.55.44"
EC2_KEY_PATH="Jecon.pem"
LOCAL_PORT=8080
REMOTE_PORT=8080
RETRY_DELAY=5  # seconds to wait before retrying
MAX_RETRIES=3  # maximum retries with same port before trying alternative

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

# Function to find an available remote port
find_available_port() {
    local base_port=$1
    local max_attempts=10
    
    for i in $(seq 0 $max_attempts); do
        local test_port=$((base_port + i))
        log_message "Testing remote port $test_port..."
        
        # Try to establish a test connection to see if port is available
        if ssh -o ConnectTimeout=5 -o BatchMode=yes -i $EC2_KEY_PATH $EC2_USER@$EC2_HOST "netstat -tln | grep :$test_port" >/dev/null 2>&1; then
            log_message "Port $test_port is in use, trying next..."
            continue
        else
            log_message "Port $test_port appears to be available"
            return $test_port
        fi
    done
    
    # If no port found, return original port
    return $base_port
}

# Function to check internet connectivity by pinging Google DNS
check_internet() {
    ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1
    return $?
}

# Ensure the key file has correct permissions
chmod 400 $EC2_KEY_PATH

log_message "Starting SSH tunnel with auto-restart capability"
log_message "Local port: $LOCAL_PORT, Remote port: $REMOTE_PORT"
log_message "Remote host: $EC2_USER@$EC2_HOST"

# Main loop to keep tunnel running
while true; do
    # Ensure we have an active internet connection before (re)establishing the tunnel
    while ! check_internet; do
        log_message "No internet connection detected. Retrying in $RETRY_DELAY seconds..."
        sleep $RETRY_DELAY
    done

    log_message "Attempting to establish SSH tunnel..."
    
    # Create the SSH tunnel with -g flag to allow remote hosts to connect
    # Capture both stdout and stderr to detect specific errors
    tunnel_output=$(ssh -N -g -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -R 0.0.0.0:$REMOTE_PORT:localhost:$LOCAL_PORT -i $EC2_KEY_PATH $EC2_USER@$EC2_HOST 2>&1)
    tunnel_exit_code=$?
    
    # Check for specific error messages
    if echo "$tunnel_output" | grep -q "remote port forwarding failed for listen port"; then
        log_message "ERROR: Remote port $REMOTE_PORT is already in use or not available"
        log_message "Tunnel output: $tunnel_output"
        
        # Try to find an alternative port
        log_message "Attempting to find an alternative port..."
        find_available_port $REMOTE_PORT
        alternative_port=$?
        
        if [ $alternative_port -ne $REMOTE_PORT ]; then
            log_message "Trying alternative port $alternative_port..."
            tunnel_output=$(ssh -N -g -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -R 0.0.0.0:$alternative_port:localhost:$LOCAL_PORT -i $EC2_KEY_PATH $EC2_USER@$EC2_HOST 2>&1)
            tunnel_exit_code=$?
            
            if [ $tunnel_exit_code -eq 0 ]; then
                log_message "SUCCESS: Tunnel established on alternative port $alternative_port"
                REMOTE_PORT=$alternative_port
            else
                log_message "ERROR: Failed to establish tunnel on alternative port $alternative_port"
                log_message "Tunnel output: $tunnel_output"
            fi
        else
            log_message "ERROR: No alternative ports available"
        fi
    elif [ $tunnel_exit_code -ne 0 ]; then
        log_message "SSH tunnel failed with exit code $tunnel_exit_code"
        log_message "Tunnel output: $tunnel_output"
    else
        log_message "SSH tunnel exited normally"
    fi
    
    log_message "Waiting $RETRY_DELAY seconds before retrying..."
    sleep $RETRY_DELAY
    
    log_message "Restarting tunnel..."
done 