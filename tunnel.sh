#!/bin/bash

# Configuration
EC2_USER="ubuntu"
EC2_HOST="3.7.55.44"
EC2_KEY_PATH="Jecon.pem"
LOCAL_PORT=8080
REMOTE_PORT=8080
RETRY_DELAY=5  # seconds to wait before retrying
MAX_RETRIES=3  # legacy variable (currently unused, tunnel always retries same port)
PING_INTERVAL=5  # seconds between connectivity checks during active tunnel

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

    # Use a temp log file so we can capture any immediate errors (e.g., port conflict)
    tunnel_log=$(mktemp)

    # Launch SSH in the background so we can monitor connectivity ourselves
    ssh -N -g \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -R 0.0.0.0:$REMOTE_PORT:localhost:$LOCAL_PORT \
        -i $EC2_KEY_PATH $EC2_USER@$EC2_HOST \
        > "$tunnel_log" 2>&1 &
    SSH_PID=$!

    # Give SSH a moment to fail fast if something is wrong (e.g., remote port already in use)
    sleep 3

    if ! kill -0 $SSH_PID 2>/dev/null; then
        # SSH process already exited – inspect the log for reasons
        tunnel_output=$(cat "$tunnel_log")
        rm -f "$tunnel_log"

        if echo "$tunnel_output" | grep -q "remote port forwarding failed for listen port"; then
            log_message "ERROR: Remote port $REMOTE_PORT is already in use or not available"

            # Attempt to free the port by terminating any existing listeners
            log_message "Attempting to free remote port $REMOTE_PORT..."
            ssh -o ConnectTimeout=5 -i $EC2_KEY_PATH $EC2_USER@$EC2_HOST "fuser -k ${REMOTE_PORT}/tcp" >/dev/null 2>&1 || true
            log_message "Waiting $RETRY_DELAY seconds before retrying..."
            sleep $RETRY_DELAY
        else
            log_message "SSH tunnel failed to start. Output: $tunnel_output"
            log_message "Waiting $RETRY_DELAY seconds before retrying..."
            sleep $RETRY_DELAY
        fi
        # Proceed to next iteration of main while-loop
        continue
    else
        log_message "SUCCESS: SSH tunnel established (PID $SSH_PID) on remote port $REMOTE_PORT"
        rm -f "$tunnel_log"
    fi

    # Monitor the tunnel and internet connectivity
    while kill -0 $SSH_PID 2>/dev/null; do
        sleep $PING_INTERVAL
        if ! check_internet; then
            log_message "Internet connection lost. Terminating SSH tunnel (PID $SSH_PID)..."
            kill $SSH_PID
            wait $SSH_PID 2>/dev/null
            break
        fi
    done

    log_message "SSH tunnel process ended or was terminated. Waiting $RETRY_DELAY seconds before retrying..."
    sleep $RETRY_DELAY

    log_message "Restarting tunnel..."
done 