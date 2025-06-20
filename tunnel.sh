#!/bin/bash

# Configuration
EC2_USER="ubuntu"
EC2_HOST="3.7.55.44"
EC2_KEY_PATH="Jecon.pem"
LOCAL_PORT=8080
REMOTE_PORT=8080

# Ensure the key file has correct permissions
chmod 400 $EC2_KEY_PATH

# Create the SSH tunnel with -g flag to allow remote hosts to connect
ssh -N -g -R 0.0.0.0:$REMOTE_PORT:localhost:$LOCAL_PORT -i $EC2_KEY_PATH $EC2_USER@$EC2_HOST 