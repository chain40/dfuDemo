
import asyncio
import os
import sys
import time
from io import BytesIO
import serial
from serial.serialutil import Timeout
import random

def main(argv):
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    ser = serial.Serial(port = argv[0], baudrate = 115200, timeout = 1.0)
   
    if ser.isOpen() == False:
        return
    
    dfu_start : int = 0
    for i in range(15):
        dfu_start = int.from_bytes(ser.read(2), byteorder='little')
        if dfu_start == 0x5555:
            break;
    if dfu_start != 0x55555555:
        print('no dfu start request')
        time.sleep(3)
        return

    print('recv dfu start')


if __name__ == "__main__":
    main(sys.argv[1:])
