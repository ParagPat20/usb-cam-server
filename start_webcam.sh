#!/bin/bash

# Change to the directory containing webcam.py
cd /home/jecon/usb-cam-server

python3 webcam.py --host 0.0.0.0 --port 8080 &

# Function to check internet connectivity
check_internet() {
    ping -c 1 8.8.8.8 >/dev/null 2>&1
    return $?
}

# Wait a few seconds for the server to start
sleep 5
# Wait for internet connection
echo "Waiting for internet connection..."
while ! check_internet; do
    sleep 5
done
echo "Internet connection established!"


# Start ngrok to expose the webcam server
ngrok http --domain=special-gnu-flexible.ngrok-free.app 8080 