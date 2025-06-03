# USB Webcam Server Setup for Raspberry Pi

This guide will help you set up a webcam server on your Raspberry Pi that streams video over the internet using ngrok.

## Prerequisites

- Raspberry Pi (3 or newer recommended)
- USB Webcam
- Internet connection
- ngrok account (free tier is sufficient)

## Installation Steps

1. **Update System**
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

2. **Install Required Packages**
   ```bash
   sudo apt install -y python3 python3-pip git
   ```

3. **Install Python Dependencies**
   ```bash
   pip3 install opencv-python flask
   ```

4. **Install ngrok**
   ```bash
   # Download ngrok
   wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz
   
   # Extract ngrok
   tar xvzf ngrok-v3-stable-linux-arm64.tgz
   
   # Move to a directory in your PATH
   sudo mv ngrok /usr/local/bin
   ```

5. **Configure ngrok**
   - Sign up for a free ngrok account at https://ngrok.com
   - Get your authtoken from the ngrok dashboard
   - Configure ngrok with your authtoken:
     ```bash
     ngrok config add-authtoken YOUR_AUTH_TOKEN
     ```

6. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/usb-cam-server.git
   cd usb-cam-server
   ```

7. **Make the Start Script Executable**
   ```bash
   chmod +x start_webcam.sh
   ```

## Running the Server

1. **Start the Server**
   ```bash
   ./start_webcam.sh
   ```

The script will:
- Start the webcam server on port 8080
- Wait for internet connectivity
- Start ngrok to expose your webcam stream

## Accessing the Webcam Stream

Once the server is running, you can access your webcam stream at:
```
https://special-gnu-flexible.ngrok-free.app
```

## Troubleshooting

1. **Webcam Not Detected**
   - Check if your webcam is recognized:
     ```bash
     ls -l /dev/video*
     ```
   - Install additional drivers if needed:
     ```bash
     sudo apt install -y v4l-utils
     ```

2. **Permission Issues**
   - Add your user to the video group:
     ```bash
     sudo usermod -a -G video $USER
     ```
   - Log out and log back in for changes to take effect

3. **Port Already in Use**
   - Check if port 8080 is already in use:
     ```bash
     sudo lsof -i :8080
     ```
   - Kill the process or change the port in the script

## Security Notes

- The current setup exposes your webcam to the internet
- Consider adding authentication to your webcam stream
- Regularly update your system and dependencies
- Monitor ngrok logs for any suspicious activity

## License

[Add your license information here] 