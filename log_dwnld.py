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
from pymavlink import mavutil

CHUNK_SIZE = 90  # Bytes per LOG_DATA payload (fixed for ArduPilot)
SILENCE_TIMEOUT = 2  # Seconds without LOG_ENTRY before we assume the list is complete

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
    parser = argparse.ArgumentParser(description="Download DataFlash logs via MAVLink")
    parser.add_argument("--port", default="/dev/serial/by-id/usb-ArduPilot_Pixhawk6X_36004E001351333031333637-if00", help="Serial port of the flight controller")
    parser.add_argument("--baud", type=int, default=115200, help="Baudrate")
    parser.add_argument("--out", default="logs", help="Destination directory for downloaded logs")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(f"[INFO] Connecting to {args.port} @ {args.baud} baud …")
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

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user - exiting.") 