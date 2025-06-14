#!/bin/bash

# Configuration
EC2_USER="ec2-user"
EC2_HOST="13.201.75.136"
EC2_KEY_PATH="ec2-key.pem"
LOCAL_PORT=8080
REMOTE_PORT=8080

# Ensure the key file has correct permissions
chmod 400 $EC2_KEY_PATH

# Create the SSH tunnel
ssh -N -R $REMOTE_PORT:localhost:$LOCAL_PORT -i $EC2_KEY_PATH $EC2_USER@$EC2_HOST 