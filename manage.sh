#!/bin/bash

# Function to check if virtual environment exists
check_venv() {
    if [ ! -d "venv" ]; then
        echo "Virtual environment not found. Setting up..."
        chmod +x setup_venv.sh
        ./setup_venv.sh
    fi
}

# Function to start webcam in tmux
start_webcam_tmux() {
    if ! tmux has-session -t webcam 2>/dev/null; then
        tmux new-session -d -s webcam
        tmux send-keys -t webcam "cd $(pwd) && source venv/bin/activate && python webcam.py" C-m
        echo "Webcam started in tmux session 'webcam'"
    else
        echo "Webcam tmux session already exists"
    fi
}

# Function to stop webcam tmux
stop_webcam_tmux() {
    if tmux has-session -t webcam 2>/dev/null; then
        tmux kill-session -t webcam
        echo "Webcam tmux session stopped"
    else
        echo "No webcam tmux session found"
    fi
}

# Function to view webcam logs
view_webcam_tmux() {
    if tmux has-session -t webcam 2>/dev/null; then
        tmux attach-session -t webcam
    else
        echo "No webcam tmux session found"
    fi
}

# Function to start tunnel in tmux
start_tunnel_tmux() {
    if ! tmux has-session -t tunnel 2>/dev/null; then
        tmux new-session -d -s tunnel
        tmux send-keys -t tunnel "cd $(pwd) && chmod +x tunnel.sh && ./tunnel.sh" C-m
        echo "Tunnel started in tmux session 'tunnel' with auto-restart capability"
    else
        echo "Tunnel tmux session already exists"
    fi
}

# Function to stop tunnel in tmux
stop_tunnel_tmux() {
    if tmux has-session -t tunnel 2>/dev/null; then
        tmux kill-session -t tunnel
        echo "Tunnel tmux session stopped"
    else
        echo "No tunnel tmux session found"
    fi
}

# Function to view tunnel logs
view_tunnel_tmux() {
    if tmux has-session -t tunnel 2>/dev/null; then
        tmux attach-session -t tunnel
    else
        echo "No tunnel tmux session found"
    fi
}

# Function to check tunnel status
check_tunnel_status() {
    if tmux has-session -t tunnel 2>/dev/null; then
        # Check if the tunnel process is still running
        if tmux list-panes -t tunnel -F "#{pane_pid}" | xargs ps -p >/dev/null 2>&1; then
            echo "Tunnel is running"
            return 0
        else
            echo "Tunnel session exists but process is not running"
            return 1
        fi
    else
        echo "No tunnel session found"
        return 1
    fi
}

# Function to restart tunnel if needed
restart_tunnel_if_needed() {
    if ! check_tunnel_status >/dev/null 2>&1; then
        echo "Tunnel is not running properly, restarting..."
        stop_tunnel_tmux
        sleep 2
        start_tunnel_tmux
        echo "Tunnel restarted"
    else
        echo "Tunnel is running properly"
    fi
}

# Function to diagnose tunnel issues
diagnose_tunnel() {
    echo "=== Tunnel Diagnosis ==="
    
    # Check if tmux session exists
    if tmux has-session -t tunnel 2>/dev/null; then
        echo "✓ Tunnel tmux session exists"
        
        # Check if process is running
        if tmux list-panes -t tunnel -F "#{pane_pid}" | xargs ps -p >/dev/null 2>&1; then
            echo "✓ Tunnel process is running"
            
            # Show recent logs
            echo "Recent tunnel logs:"
            tmux capture-pane -t tunnel -p | tail -10
        else
            echo "✗ Tunnel session exists but process is not running"
        fi
    else
        echo "✗ No tunnel tmux session found"
    fi
    
    # Check if local service is running on port 8080
    echo "Checking local service on port 8080..."
    if netstat -tln 2>/dev/null | grep -q ":8080 "; then
        echo "✓ Local service is running on port 8080"
        # Try to identify what's running on port 8080
        local_pid=$(netstat -tlnp 2>/dev/null | grep ":8080 " | awk '{print $7}' | cut -d'/' -f1)
        if [ -n "$local_pid" ]; then
            local_process=$(ps -p $local_pid -o comm= 2>/dev/null)
            echo "  Process: $local_process (PID: $local_pid)"
        fi
    else
        echo "✗ No local service running on port 8080"
        echo "  This is likely causing the 'Gateway timeout' error"
        echo "  Start the webcam service first: ./manage.sh start-webcam"
    fi
    
    # Check SSH key permissions
    if [ -f "Jecon.pem" ]; then
        perms=$(stat -c "%a" Jecon.pem 2>/dev/null || stat -f "%Lp" Jecon.pem 2>/dev/null)
        if [ "$perms" = "400" ]; then
            echo "✓ SSH key has correct permissions (400)"
        else
            echo "✗ SSH key has incorrect permissions ($perms), should be 400"
            echo "  Run: chmod 400 Jecon.pem"
        fi
    else
        echo "✗ SSH key file (Jecon.pem) not found"
    fi
    
    # Test SSH connectivity
    echo "Testing SSH connectivity..."
    if ssh -o ConnectTimeout=10 -o BatchMode=yes -i Jecon.pem ubuntu@3.7.55.44 "echo 'SSH connection successful'" 2>/dev/null; then
        echo "✓ SSH connection to remote host successful"
    else
        echo "✗ SSH connection to remote host failed"
        echo "  Check your internet connection and SSH key"
    fi
    
    # Check if remote port is in use
    echo "Checking remote port 8080..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes -i Jecon.pem ubuntu@3.7.55.44 "netstat -tln | grep :8080" >/dev/null 2>&1; then
        echo "✗ Remote port 8080 is already in use"
        echo "  This is likely causing the 'remote port forwarding failed' error"
        echo "  The tunnel script will attempt to free the port and retry on port 8080"
    else
        echo "✓ Remote port 8080 appears to be available"
    fi
}

# Function to start MR72 MAVLink in tmux
start_mr72_tmux() {
    if ! tmux has-session -t mr72 2>/dev/null; then
        tmux new-session -d -s mr72
        tmux send-keys -t mr72 "cd $(pwd) && source venv/bin/activate && python mr72_mavlink.py" C-m
        echo "MR72 MAVLink started in tmux session 'mr72'"
    else
        echo "MR72 MAVLink tmux session already exists"
    fi
}

# Function to stop MR72 MAVLink tmux
stop_mr72_tmux() {
    if tmux has-session -t mr72 2>/dev/null; then
        tmux kill-session -t mr72
        echo "MR72 MAVLink tmux session stopped"
    else
        echo "No MR72 MAVLink tmux session found"
    fi
}

# Function to view MR72 MAVLink logs
view_mr72_tmux() {
    if tmux has-session -t mr72 2>/dev/null; then
        tmux attach-session -t mr72
    else
        echo "No MR72 MAVLink tmux session found"
    fi
}

# Function to start all in tmux
start_all_tmux() {
    start_webcam_tmux
    start_tunnel_tmux
    start_mr72_tmux
    echo "All services started in tmux"
}

# Function to stop all tmux sessions
stop_all_tmux() {
    stop_webcam_tmux
    stop_tunnel_tmux
    stop_mr72_tmux
    echo "All tmux sessions stopped"
}

# Function to view all tmux sessions
list_tmux() {
    echo "=== Active Tmux Sessions ==="
    tmux ls
}

# Function to install startup service
install_startup() {
    sudo cp startup.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable startup.service
    echo "Startup service installed and enabled"
}

# Function to check local service status
check_local_service() {
    echo "=== Local Service Status ==="
    
    # Check if webcam service is running
    if tmux has-session -t webcam 2>/dev/null; then
        echo "✓ Webcam tmux session exists"
        if tmux list-panes -t webcam -F "#{pane_pid}" | xargs ps -p >/dev/null 2>&1; then
            echo "✓ Webcam process is running"
        else
            echo "✗ Webcam session exists but process is not running"
        fi
    else
        echo "✗ No webcam tmux session found"
    fi
    
    # Check if port 8080 is listening
    if netstat -tln 2>/dev/null | grep -q ":8080 "; then
        echo "✓ Port 8080 is listening"
        local_pid=$(netstat -tlnp 2>/dev/null | grep ":8080 " | awk '{print $7}' | cut -d'/' -f1)
        if [ -n "$local_pid" ]; then
            local_process=$(ps -p $local_pid -o comm= 2>/dev/null)
            echo "  Process: $local_process (PID: $local_pid)"
        fi
    else
        echo "✗ Port 8080 is not listening"
        echo "  Start the webcam service: ./manage.sh start-webcam"
    fi
    
    # Test local connection
    echo "Testing local connection to port 8080..."
    if curl -s --connect-timeout 5 http://localhost:8080 >/dev/null 2>&1; then
        echo "✓ Local service responds on port 8080"
    else
        echo "✗ Local service does not respond on port 8080"
        echo "  This will cause 'Gateway timeout' errors when accessing the tunnel"
    fi
}

# Function to show comprehensive status
show_status() {
    echo "=== COMPREHENSIVE SYSTEM STATUS ==="
    echo ""
    
    # Check local service
    check_local_service
    echo ""
    
    # Check tunnel
    echo "=== Tunnel Status ==="
    if tmux has-session -t tunnel 2>/dev/null; then
        echo "✓ Tunnel tmux session exists"
        if tmux list-panes -t tunnel -F "#{pane_pid}" | xargs ps -p >/dev/null 2>&1; then
            echo "✓ Tunnel process is running"
        else
            echo "✗ Tunnel session exists but process is not running"
        fi
    else
        echo "✗ No tunnel tmux session found"
    fi
    
    # Check if tunnel port is listening on remote
    echo "Checking remote tunnel port..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes -i Jecon.pem ubuntu@3.7.55.44 "netstat -tln | grep :8080" >/dev/null 2>&1; then
        echo "✓ Remote port 8080 is listening (tunnel is active)"
    else
        echo "✗ Remote port 8080 is not listening"
        echo "  Tunnel may not be working properly"
    fi
    
    echo ""
    echo "=== Summary ==="
    
    # Determine overall status
    local_running=false
    tunnel_running=false
    
    if netstat -tln 2>/dev/null | grep -q ":8080 "; then
        local_running=true
    fi
    
    if tmux has-session -t tunnel 2>/dev/null && tmux list-panes -t tunnel -F "#{pane_pid}" | xargs ps -p >/dev/null 2>&1; then
        tunnel_running=true
    fi
    
    if [ "$local_running" = true ] && [ "$tunnel_running" = true ]; then
        echo "✅ SYSTEM IS WORKING - Both local service and tunnel are running"
        echo "   You should be able to access: http://3.7.55.44:8080"
    elif [ "$local_running" = true ] && [ "$tunnel_running" = false ]; then
        echo "⚠️  PARTIAL - Local service is running but tunnel is not"
        echo "   Run: ./manage.sh start-tunnel"
    elif [ "$local_running" = false ] && [ "$tunnel_running" = true ]; then
        echo "⚠️  PARTIAL - Tunnel is running but local service is not"
        echo "   This will cause 'Gateway timeout' errors"
        echo "   Run: ./manage.sh start-webcam"
    else
        echo "❌ NOT WORKING - Neither local service nor tunnel is running"
        echo "   Run: ./manage.sh start-all"
    fi
}

# Function to diagnose EC2 nginx configuration
diagnose_ec2_nginx() {
    echo "=== EC2 Nginx Diagnosis ==="
    
    # Check if nginx is running on EC2
    echo "Checking nginx status on EC2..."
    if ssh -o ConnectTimeout=10 -i Jecon.pem ubuntu@3.7.55.44 "sudo systemctl is-active nginx" 2>/dev/null; then
        echo "✓ Nginx is running on EC2"
    else
        echo "✗ Nginx is not running on EC2"
        echo "  Run: ./manage.sh fix-ec2-nginx"
        return 1
    fi
    
    # Check nginx configuration
    echo "Checking nginx configuration..."
    if ssh -o ConnectTimeout=10 -i Jecon.pem ubuntu@3.7.55.44 "sudo nginx -t" 2>/dev/null; then
        echo "✓ Nginx configuration is valid"
    else
        echo "✗ Nginx configuration has errors"
        echo "  Run: ./manage.sh fix-ec2-nginx"
        return 1
    fi
    
    # Check if nginx is configured to proxy to port 8080
    echo "Checking nginx proxy configuration..."
    nginx_config=$(ssh -o ConnectTimeout=10 -i Jecon.pem ubuntu@3.7.55.44 "sudo cat /etc/nginx/sites-available/default 2>/dev/null || sudo cat /etc/nginx/nginx.conf 2>/dev/null")
    
    if echo "$nginx_config" | grep -q "proxy_pass.*8080"; then
        echo "✓ Nginx is configured to proxy to port 8080"
    else
        echo "✗ Nginx is NOT configured to proxy to port 8080"
        echo "  This is likely the cause of the gateway timeout"
        echo "  Run: ./manage.sh fix-ec2-nginx"
        return 1
    fi
    
    # Check if port 80 is open in security group
    echo "Testing external access to port 80..."
    if curl -s --connect-timeout 10 http://3.7.55.44 >/dev/null 2>&1; then
        echo "✓ Port 80 is accessible externally"
    else
        echo "✗ Port 80 is not accessible externally"
        echo "  Check EC2 security group settings"
    fi
    
    # Test direct access to port 8080
    echo "Testing direct access to port 8080..."
    if curl -s --connect-timeout 10 http://3.7.55.44:8080 >/dev/null 2>&1; then
        echo "✓ Port 8080 is accessible directly"
        echo "  The tunnel is working correctly"
    else
        echo "✗ Port 8080 is not accessible directly"
        echo "  This suggests a firewall/security group issue"
    fi
    
    echo ""
    echo "=== Recommendations ==="
    echo "1. If nginx is not configured properly, run: ./manage.sh fix-ec2-nginx"
    echo "2. If port 80 is not accessible, check EC2 security group inbound rules"
    echo "3. If port 8080 is not accessible, check EC2 security group inbound rules"
}

# Function to fix EC2 nginx configuration
fix_ec2_nginx() {
    echo "=== Fixing EC2 Nginx Configuration ==="
    
    # Create nginx configuration that proxies to port 8080
    nginx_config='server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for WebRTC
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}'
    
    echo "Creating nginx configuration..."
    ssh -o ConnectTimeout=10 -i Jecon.pem ubuntu@3.7.55.44 "echo '$nginx_config' | sudo tee /etc/nginx/sites-available/default > /dev/null"
    
    echo "Testing nginx configuration..."
    if ssh -o ConnectTimeout=10 -i Jecon.pem ubuntu@3.7.55.44 "sudo nginx -t"; then
        echo "✓ Nginx configuration is valid"
        
        echo "Reloading nginx..."
        if ssh -o ConnectTimeout=10 -i Jecon.pem ubuntu@3.7.55.44 "sudo systemctl reload nginx"; then
            echo "✓ Nginx reloaded successfully"
            echo ""
            echo "✅ Nginx is now configured to proxy requests to port 8080"
            echo "   Try accessing: http://3.7.55.44 (without port number)"
        else
            echo "✗ Failed to reload nginx"
        fi
    else
        echo "✗ Nginx configuration is invalid"
        echo "  Check the configuration manually"
    fi
}

# Function to check EC2 security group
check_ec2_security() {
    echo "=== EC2 Security Group Check ==="
    
    echo "Checking if port 80 is open..."
    if curl -s --connect-timeout 10 http://3.7.55.44 >/dev/null 2>&1; then
        echo "✓ Port 80 is accessible"
    else
        echo "✗ Port 80 is not accessible"
        echo "  Add inbound rule: HTTP (80) from 0.0.0.0/0"
    fi
    
    echo "Checking if port 8080 is open..."
    if curl -s --connect-timeout 10 http://3.7.55.44:8080 >/dev/null 2>&1; then
        echo "✓ Port 8080 is accessible"
    else
        echo "✗ Port 8080 is not accessible"
        echo "  Add inbound rule: Custom TCP (8080) from 0.0.0.0/0"
    fi
    
    echo ""
    echo "=== Security Group Configuration ==="
    echo "In your EC2 console, ensure these inbound rules exist:"
    echo "1. HTTP (80) - Source: 0.0.0.0/0"
    echo "2. Custom TCP (8080) - Source: 0.0.0.0/0 (if you want direct access)"
    echo "3. SSH (22) - Source: Your IP or 0.0.0.0/0"
}

# Function to download logs from the flight-controller via MAVLink
# This will pause the MR72 bridge (tmux session "mr72") while the serial
# link is in use, run the Python downloader, then resume the bridge.
download_logs() {
    mkdir -p logs  # make sure destination exists

    # Pause MR72 session if running
    local mr72_was_running=false
    if tmux has-session -t mr72 2>/dev/null; then
        mr72_was_running=true
        echo "Pausing MR72 MAVLink session…"
        stop_mr72_tmux
        sleep 2  # allow serial port to free
    fi

    # Activate virtual-env if available
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    echo "Starting log download (this may take a while)…"
    python3 log_dwnld.py --out logs
    local dl_status=$?

    # Deactivate venv if we activated it
    if [ -n "$VIRTUAL_ENV" ]; then
        deactivate
    fi

    # Resume MR72 session if it was previously running
    if [ "$mr72_was_running" = true ]; then
        echo "Resuming MR72 MAVLink session…"
        start_mr72_tmux
    fi

    return $dl_status
}

# Function to expose a single log file over a temporary HTTP server so it can
# be downloaded to a laptop. Usage: ./manage.sh ftplog <log_filename>
ftplog() {
    local log_name="$1"
    if [ -z "$log_name" ]; then
        echo "Usage: $0 ftplog {log_name}"
        return 1
    fi

    if [ ! -f "logs/$log_name" ]; then
        echo "Log file logs/$log_name not found"
        return 1
    fi

    # Start a lightweight HTTP server in the background
    pushd logs >/dev/null || return 1
    echo "Starting temporary HTTP server on port 9000 …"
    python3 -m http.server 9000 &
    local server_pid=$!
    popd >/dev/null

    local ip=$(hostname -I | awk '{print $1}')
    echo "==============================================="
    echo "Download URL: http://$ip:9000/$log_name"
    echo "Press <ENTER> once the download is complete to stop the server."
    echo "==============================================="
    read -r _
    kill $server_pid
    echo "HTTP server stopped."
}

# Main script
case "$1" in
    "start-webcam")
        start_webcam_tmux
        ;;
    "stop-webcam")
        stop_webcam_tmux
        ;;
    "view-webcam")
        view_webcam_tmux
        ;;
    "start-tunnel")
        start_tunnel_tmux
        ;;
    "stop-tunnel")
        stop_tunnel_tmux
        ;;
    "view-tunnel")
        view_tunnel_tmux
        ;;
    "check-tunnel")
        check_tunnel_status
        ;;
    "restart-tunnel")
        restart_tunnel_if_needed
        ;;
    "start-mr72")
        start_mr72_tmux
        ;;
    "stop-mr72")
        stop_mr72_tmux
        ;;
    "view-mr72")
        view_mr72_tmux
        ;;
    "start-all")
        start_all_tmux
        ;;
    "stop-all")
        stop_all_tmux
        ;;
    "list")
        list_tmux
        ;;
    "install-startup")
        install_startup
        ;;
    "setup")
        check_venv
        ;;
    "diagnose-tunnel")
        diagnose_tunnel
        ;;
    "check-local-service")
        check_local_service
        ;;
    "show-status")
        show_status
        ;;
    "diagnose-ec2-nginx")
        diagnose_ec2_nginx
        ;;
    "fix-ec2-nginx")
        fix_ec2_nginx
        ;;
    "check-ec2-security")
        check_ec2_security
        ;;
    "download-logs")
        download_logs
        ;;
    "ftplog")
        shift
        ftplog "$1"
        ;;
    *)
        echo "Usage: $0 {start-webcam|stop-webcam|view-webcam|start-tunnel|stop-tunnel|view-tunnel|check-tunnel|restart-tunnel|start-mr72|stop-mr72|view-mr72|download-logs|ftplog|start-all|stop-all|list|install-startup|setup|diagnose-tunnel|check-local-service|show-status|diagnose-ec2-nginx|fix-ec2-nginx|check-ec2-security}"
        exit 1
        ;;
esac 