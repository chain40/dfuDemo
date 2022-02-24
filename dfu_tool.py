import asyncio
from asyncio.windows_events import NULL
from math import fabs
import os
from pickle import NONE
import sys
import time
from tkinter.filedialog import Open
from tkinter.tix import Tree
from turtle import bye
from typing import Type
import serial
from serial.serialutil import Timeout
import random
from io import BufferedReader

DFU_START_REQ = 0x5555
DFU_SIZE_REQ = 0x0001
DFU_CHKSUM_REQ = 0x0002
DFU_SEG_DATA_REQ = 0x0003
DFU_SEG_CHKSUM_REQ = 0x0004
DFU_ABORD_REQ = 0x00EE
DFU_CPLT_REQ = 0x00FF

DFU_START_RSP = 0xCC33
DFU_MAGIC_VALUE = 0x12345678

SPL_PREAMBLE = 0xAAAA


def ChkSumCal(raw: tuple()) -> int:
    chksum = 0
    for i in raw:
        chksum += i
    return chksum % 0x10000


def SplSend(ser: serial.Serial, send_data: tuple()):
    buf = []
    buf += SPL_PREAMBLE.to_bytes(2, byteorder="little")
    buf += len(send_data).to_bytes(2, byteorder="little")
    buf += send_data
    buf += ChkSumCal(send_data).to_bytes(2, byteorder="little")
    ser.write(buf)


class Request(object):
    def __init__(self, id: int, data: tuple()):
        self.req: int = id
        self.reqData: tuple() = data

    def GetID(self) -> int:
        return self.req

    def GetParam(self) -> tuple():
        return self.reqData


def SplRecv(ser: serial.Serial):
    preamble = int.from_bytes(ser.read(2), byteorder="little")
    if preamble != SPL_PREAMBLE:
        return NULL
    recv_size = int.from_bytes(ser.read(2), byteorder="little")
    recv_data = ser.read(recv_size)
    chk_sum = int.from_bytes(ser.read(2), byteorder="little")
    if chk_sum == ChkSumCal(recv_data):
        return Request(int.from_bytes(recv_data[:2], byteorder="little"), recv_data[2:])
    return NULL

def resp_dfu_start(ser: serial.Serial, req: Request, dummy=None):
    send = DFU_START_RSP.to_bytes(2, byteorder="little")
    SplSend(ser, send)
    return True


def resp_dfu_size(ser: serial.Serial, req: Request, f: BufferedReader):
    fileSize = f.seek(0, 2)
    send = fileSize.to_bytes(4, byteorder="little")
    SplSend(ser, send)
    print("[total data size evt] binary file size = {0} bytes".format(fileSize))
    return True


def resp_dfu_chksum(ser: serial.Serial, req: Request, f: BufferedReader):
    f.seek(0, 0)
    all_of_it = f.read()
    chksum = ChkSumCal(all_of_it)
    send = chksum.to_bytes(2, byteorder="little")
    SplSend(ser, send[:2])
    print("[total data chksum evt] binary checksum = {0}".format(chksum))
    return True


def resp_seg_data(ser: serial.Serial, req: Request, f: BufferedReader):
    raw = req.GetParam()
    offset = int.from_bytes(raw[0:4], byteorder="little")
    size = int.from_bytes(raw[4:8], byteorder="little")
    print("[segment data request evt] offset = 0x{0:08X}, size = {1} bytes".format(offset, size))
    f.seek(offset, 0)
    seg = f.read(size)
    SplSend(ser, seg)
    return True


def resp_seg_chksum(ser: serial.Serial, req: Request, f: BufferedReader):
    raw = req.GetParam()
    offset = int.from_bytes(raw[0:4], byteorder="little")
    size = int.from_bytes(raw[4:8], byteorder="little")
    f.seek(offset, 0)
    seg = f.read(size)
    chksum = ChkSumCal(seg)
    send = chksum.to_bytes(2, byteorder="little")
    SplSend(ser, send[:2])
    return True

def resp_abort(ser: serial.Serial, req: Request, f: BufferedReader=NONE):
    print("[dfu abort evt]")
    return False

def resp_cplt(ser: serial.Serial, req: Request, f: BufferedReader=NONE):
    print("[dfu complete evt]")
    return False

callback = {
    DFU_START_REQ: resp_dfu_start,
    DFU_SIZE_REQ: resp_dfu_size,
    DFU_CHKSUM_REQ: resp_dfu_chksum,
    DFU_SEG_DATA_REQ: resp_seg_data,
    DFU_SEG_CHKSUM_REQ: resp_seg_chksum,
    DFU_ABORD_REQ: resp_abort,
    DFU_CPLT_REQ: resp_cplt,
}


def main(argv):
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    ser = serial.Serial(port=argv[0], baudrate=115200, timeout=4.0)

    if ser.isOpen() == False:
        return

    send = DFU_MAGIC_VALUE.to_bytes(4, byteorder="little")
    SplSend(ser, send)

    for i in range(10):
        req = SplRecv(ser)
        if req != NULL:
            if req.GetID() == DFU_START_REQ:
                break

    if req == NULL:
        print("wait request timeout.")
        time.sleep(3)
        return

    if req.GetID() != DFU_START_REQ:
        print("wait request timeout.")
        time.sleep(3)
        return

    print("[dfu start evt]")

    resp_dfu_start(ser, req)

    with open(argv[1], "rb") as f:
        IsKeppAlive = True
        while IsKeppAlive:
            req = SplRecv(ser)
            if req == NULL:
                IsKeppAlive = False
                print("wait request timeout.")
            else:
                IsKeppAlive = callback.get(req.GetID())(ser, req, f)


if __name__ == "__main__":
    main(sys.argv[1:])
    input("Press Any Key To Exit...")