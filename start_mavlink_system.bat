@echo off
REM MR72 Radar + MAVProxy Startup Script for Windows
REM This script starts both MAVProxy and the MR72-MAVLink bridge

setlocal enabledelayedexpansion

REM Configuration
set GCS_IP=192.168.1.100
set MAVPROXY_PORT=14550
set BRIDGE_PORT=14551
set RADAR_PORT=COM3
set FLIGHT_CONTROLLER_PORT=COM1
set BAUDRATE=115200

echo MR72 Radar + MAVProxy Startup Script
echo =====================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python first.
    pause
    exit /b 1
)

REM Check if required packages are installed
python -c "import pymavlink, serial" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Required Python packages not found.
    echo Install with: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Check if mavproxy is installed
mavproxy.py --help >nul 2>&1
if errorlevel 1 (
    echo ERROR: MAVProxy not found. Please install MAVProxy first.
    echo Install with: pip install mavproxy
    pause
    exit /b 1
)

echo Prerequisites check complete.

REM Kill any existing processes
echo Stopping any existing processes...
taskkill /f /im mavproxy.py >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 >nul

REM Start MAVProxy
echo Starting MAVProxy...
echo MAVProxy command: mavproxy.py --master=%FLIGHT_CONTROLLER_PORT% --baudrate=%BAUDRATE% --out=udp:%GCS_IP%:%MAVPROXY_PORT% --out=udp:127.0.0.1:%BRIDGE_PORT%

start "MAVProxy" cmd /c "mavproxy.py --master=%FLIGHT_CONTROLLER_PORT% --baudrate=%BAUDRATE% --out=udp:%GCS_IP%:%MAVPROXY_PORT% --out=udp:127.0.0.1:%BRIDGE_PORT%"

REM Wait for MAVProxy to start
timeout /t 3 >nul

REM Start MR72-MAVLink bridge
echo Starting MR72-MAVLink bridge...
echo Bridge command: python mr72_mavlink.py --radar-port=%RADAR_PORT% --mavlink-port=%BRIDGE_PORT%

start "MR72 Bridge" cmd /c "python mr72_mavlink.py --radar-port=%RADAR_PORT% --mavlink-port=%BRIDGE_PORT%"

REM Wait for bridge to start
timeout /t 2 >nul

echo.
echo System started successfully!
echo MAVProxy: Running in separate window
echo Bridge: Running in separate window
echo GCS connection: udp://%GCS_IP%:%MAVPROXY_PORT%
echo Bridge connection: udp://127.0.0.1:%BRIDGE_PORT%
echo Radar port: %RADAR_PORT%
echo Flight controller port: %FLIGHT_CONTROLLER_PORT%
echo.
echo Press any key to stop all services...

pause

REM Cleanup
echo Stopping services...
taskkill /f /im mavproxy.py >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
echo Cleanup complete.
pause 