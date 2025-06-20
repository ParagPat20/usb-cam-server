# Configuration
$EC2_USER="ubuntu"
$EC2_HOST="3.7.55.44"
$EC2_KEY_PATH=".\Jecon.pem" # Assumes Jecon.pem is in the same directory
$LOCAL_PORT=8080
$REMOTE_PORT=8080

# --- IMPORTANT ---
# The native OpenSSH client on Windows requires that the private key file
# is only accessible by you. You must set permissions on the .pem file.
#
# To do this manually (easiest method):
# 1. Right-click on your 'Jecon.pem' file in File Explorer.
# 2. Go to Properties -> Security tab -> Advanced.
# 3. Click "Disable inheritance" and then "Remove all inherited permissions from this object".
# 4. Click "Add", then "Select a principal", type your Windows username, and click OK.
# 5. Grant your user "Read" permissions, and click OK on all windows.
#
# If you don't do this, the SSH command will fail with a permissions error.

Write-Host "Starting SSH tunnel..."
Write-Host "Local Port: $LOCAL_PORT"
Write-Host "Remote Port: $REMOTE_PORT"
Write-Host "EC2 Host: $EC2_HOST"
Write-Host "Press Ctrl+C to stop the tunnel."

# The ssh.exe command is identical to the one in the bash script.
# It should be available if you have the OpenSSH Client feature installed on Windows 10/11.
ssh -N -g -R "0.0.0.0:${REMOTE_PORT}:localhost:${LOCAL_PORT}" -i $EC2_KEY_PATH "${EC2_USER}@${EC2_HOST}" 