#!/usr/bin/env python3
"""
log_dwnld.py – Download all DataFlash logs from a flight-controller over MAVLink.

Usage:
    python log_dwnld.py [--port SERIAL_DEV] [--baud BAUDRATE] [--out DIR]

The script will:
1. Connect to the flight-controller.
2. Request a list of all available logs.
3. Download each log to the chosen output directory (default: ./logs).
4. Send a MAV_CMD_LOG_ERASE command to clear the log storage once the download is finished.

It is based on the standard MAVLink LOG_REQUEST_* sequence and should work on
any ArduPilot/PX4 board that supports the LOG_DOWNLOAD protocol.
"""

import os
import time
import argparse

# Try to use MAVSDK for high-speed MAVFTP. Fall back to PyMAVLink if MAVSDK is
# not available (or connection fails).
try:
    import asyncio
    from mavsdk import System  # type: ignore
    MavsdkAvailable = True
except ImportError:
    MavsdkAvailable = False

from pymavlink import mavutil

CHUNK_SIZE = 90  # Bytes per LOG_DATA payload (fixed for ArduPilot)
SILENCE_TIMEOUT = 2  # Seconds without LOG_ENTRY before we assume the list is complete

# Default DataFlash log directory for ArduPilot when accessed via MAVFTP
APM_LOG_DIR = "/APM/LOGS"

def request_log_list(mav):
    """Return a dict {log_id: size_bytes}."""
    mav.mav.log_request_list_send(mav.target_system, mav.target_component, 0, 0xFFFF)
    logs = {}
    last_msg = time.time()
    print("[INFO] Requesting log list…")

    while True:
        msg = mav.recv_match(type="LOG_ENTRY", timeout=1)
        if msg:
            logs[msg.id] = msg.size
            print(f"  ▹ Log {msg.id}: {msg.size/1024:.1f} kB (UTC {msg.time_utc})")
            last_msg = time.time()
        elif time.time() - last_msg > SILENCE_TIMEOUT:
            break  # no more entries
    return logs

def download_log(mav, log_id: int, size: int, out_path: str):
    print(f"[INFO] Downloading log {log_id} ({size/1024:.1f} kB)…")
    start_time = time.time()
    with open(out_path, "wb") as fh:
        ofs = 0
        last_print = time.time()
        while ofs < size:
            mav.mav.log_request_data_send(mav.target_system, mav.target_component, log_id, ofs, CHUNK_SIZE)
            while True:
                msg = mav.recv_match(type="LOG_DATA", blocking=True, timeout=5)
                if msg is None:
                    print("\n[WARN] Timeout, re-requesting chunk…")
                    mav.mav.log_request_data_send(mav.target_system, mav.target_component, log_id, ofs, CHUNK_SIZE)
                    continue
                if msg.id != log_id or msg.ofs != ofs:
                    # not the chunk we asked for - ignore
                    continue
                fh.write(bytes(msg.data[: msg.count]))
                ofs += msg.count
                break
            # progress output
            if time.time() - last_print > 1:
                pct = ofs / size * 100.0
                elapsed = time.time() - start_time
                speed_kBps = (ofs / 1024) / elapsed if elapsed > 0 else 0
                print(f"  ↳ {pct:.1f}% ({ofs}/{size} bytes) | {speed_kBps:.1f} kB/s", end="\r")
                last_print = time.time()
    print(f"\n[OK] Log {log_id} saved to {out_path}")

def erase_logs(mav):
    print("[INFO] Erasing logs on vehicle…")
    mav.mav.command_long_send(
        mav.target_system,
        mav.target_component,
        mavutil.mavlink.MAV_CMD_LOG_ERASE,
        0, 0, 0, 0, 0, 0, 0, 0,
    )
    ack = mav.recv_match(type="COMMAND_ACK", timeout=5)
    if ack and ack.command == mavutil.mavlink.MAV_CMD_LOG_ERASE and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
        print("[OK] Logs erased successfully.")
    else:
        print("[WARN] Did not receive ACK for log erase (or it was rejected).")

def main():
    parser = argparse.ArgumentParser(description="Download DataFlash logs (prefers MAVFTP for speed)")
    parser.add_argument("--port", default="/dev/serial/by-id/usb-ArduPilot_Pixhawk6X_36004E001351333031333637-if00", help="Serial port of the flight controller")
    parser.add_argument("--baud", type=int, default=115200, help="Baudrate")
    parser.add_argument("--out", default="logs", help="Destination directory for downloaded logs")
    parser.add_argument("--no-ftp", action="store_true", help="Force classic LOG_REQUEST download (debug)")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    if MavsdkAvailable and not args.no_ftp:
        try:
            asyncio.run(ftp_download(args))
            return
        except Exception as exc:
            print(f"[WARN] MAVFTP failed ({exc}). Falling back to LOG_REQUEST method…")

    # Fallback to slow LOG_REQUEST_DATA method
    print(f"[INFO] Connecting (PyMAVLink) to {args.port} @ {args.baud} baud …")
    mav = mavutil.mavlink_connection(args.port, baud=args.baud, source_system=255)
    mav.wait_heartbeat()
    print("[OK] Heartbeat received - FC link established.")

    logs = request_log_list(mav)
    if not logs:
        print("[INFO] No logs found on the vehicle.")
        return

    for log_id in sorted(logs):
        size = logs[log_id]
        out_file = os.path.join(args.out, f"log_{log_id}.BIN")
        if os.path.exists(out_file):
            print(f"[SKIP] {out_file} already exists - skipping.")
            continue
        download_log(mav, log_id, size, out_file)

    erase_logs(mav)

# -----------------------------------------------------------------------------
# MAVFTP implementation using MAVSDK
# -----------------------------------------------------------------------------

async def ftp_download(args):
    """Download logs using MAVFTP via MAVSDK for high-speed transfer."""

    system = System()
    conn_str = f"serial://{args.port}:{args.baud}"
    print(f"[INFO] [MAVFTP] Connecting via {conn_str}…")
    await system.connect(system_address=conn_str)

    # Wait for system to connect
    async for state in system.core.connection_state():
        if state.is_connected:
            print("[OK] [MAVFTP] System discovered.")
            break

    ftp = system.ftp

    # Verify FTP capability (optional)
    try:
        await ftp.reset()
    except Exception:
        print("[ERROR] [MAVFTP] FTP reset failed. Trying anyway…")

    # ------------------------------------------------------------------
    # Locate log files. First try common directories; if not found, walk
    # the filesystem starting from root and collect *.BIN files.
    # ------------------------------------------------------------------

    log_entries = []  # list of tuples (remote_path, size)

    async def add_logs_in_dir(path: str):
        try:
            data = await ftp.list_directory(path)
        except Exception:
            return False
        for f in getattr(data, "files", []):
            if f.name.lower().endswith(".bin"):
                full = f"{path}/{f.name}" if path else f.name
                log_entries.append((full, getattr(f, "size", 0)))
        return True

    # First probe typical locations
    for d in [APM_LOG_DIR, "/LOGS", "LOGS"]:
        if await add_logs_in_dir(d):
            # if we found any logs in this directory, no need to probe others
            if log_entries:
                break

    # If still nothing, walk recursively from root "" (or "/")
    if not log_entries:
        print("[INFO] [MAVFTP] Searching entire filesystem for *.BIN logs …")

        stack = [""]  # start at FTP root
        visited = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            try:
                data = await ftp.list_directory(current)
            except Exception:
                continue

            # enqueue subdirectories
            for d in getattr(data, "dirs", []):
                sub = f"{current}/{d.name}" if current else d.name
                stack.append(sub)

            for f in getattr(data, "files", []):
                if f.name.lower().endswith(".bin"):
                    full = f"{current}/{f.name}" if current else f.name
                    log_entries.append((full, getattr(f, "size", 0)))

    if not log_entries:
        raise RuntimeError("Could not locate any *.BIN log files via MAVFTP")

    for remote_path, size in log_entries:
        fname = os.path.basename(remote_path)
        local_path = os.path.join(args.out, fname)

        if os.path.exists(local_path):
            print(f"[SKIP] {local_path} already exists - skipping.")
            continue

        print(f"[INFO] [MAVFTP] Downloading {fname} ({size/1024:.1f} kB)…")

        start_time = time.time()

        async for prog in ftp.download(remote_path, args.out, use_burst=True):
            pct = prog.bytes_transferred / prog.total_bytes * 100.0
            elapsed = time.time() - start_time
            speed = (prog.bytes_transferred / 1024) / elapsed if elapsed > 0 else 0
            print(f"  ↳ {pct:.1f}% ({prog.bytes_transferred}/{prog.total_bytes} bytes) | {speed:.1f} kB/s", end="\r")

        print(f"\n[OK] [MAVFTP] Saved to {local_path}")

        # Remove remote after download to free space
        try:
            await ftp.remove_file(remote_path)
            print("      Remote file deleted.")
        except Exception as e:
            print(f"      [WARN] Failed to delete remote file: {e}")

    print("[INFO] [MAVFTP] All logs downloaded.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user - exiting.") 