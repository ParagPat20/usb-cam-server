import serial

ser = serial.Serial("/dev/ttyS0", 115200, timeout=1)

while True:
    frame = ser.read(19)
    print(frame) 