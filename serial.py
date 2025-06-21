import serial
import time
from serial.tools import list_ports

# Known USB VID/PIDs (update as needed)
FC_VID_PID = (0x0483, 0x5740)    # Example: STMicro STM32 (common in FCs)
MR72_VID_PID = (0x10C4, 0xEA60)  # Example: CP210x chip used by MR72

def find_ports_by_vid_pid(vid_pid):
    matching = []
    for port in list_ports.comports():
        if (port.vid, port.pid) == vid_pid:
            matching.append(port.device)
    return matching

def auto_detect_ports():
    fc_ports = find_ports_by_vid_pid(FC_VID_PID)
    mr_ports = find_ports_by_vid_pid(MR72_VID_PID)

    if not fc_ports or not mr_ports:
        print("VID/PID detection incomplete. Falling back to handshake method.")
        all_ports = [p.device for p in list_ports.comports()]
        for p in all_ports:
            try:
                ser = serial.Serial(p, 115200, timeout=0.5)
                ser.write(b'\n')
                resp = ser.readline()
                ser.close()
                if b'MAV' in resp:  # common in MAVLink FC responses
                    fc_ports.append(p)
                elif resp:
                    mr_ports.append(p)
            except:
                pass

    return fc_ports[:1], mr_ports[:1]  # return first found of each

if __name__ == "__main__":
    fc, mr = auto_detect_ports()
    print(f"Flight Controller port(s): {fc or 'None found'}")
    print(f"MR72 sensor port(s): {mr or 'None found'}")
