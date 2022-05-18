from math import fabs
import sys
from tkinter.filedialog import Open
from tkinter.tix import Tree
import serial
from serial.serialutil import Timeout
from io import BufferedReader
import sys
import serial
from serial.serialutil import Timeout
import os


def CRC16(data: bytes, poly: hex = 0xA001) -> bytes:
    """
    CRC-16 MODBUS HASHING ALGORITHM
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ poly if (crc & 0x0001) else crc >> 1
    return crc


SPL_PREAMBLE = 0x5A


def SplSend(ser: serial.Serial, send_data: tuple(), idx: int, crc16: bytes):
    buf = []
    buf += SPL_PREAMBLE.to_bytes(1, byteorder="little")
    buf += [0xA1]
    buf += (len(send_data) + 4).to_bytes(1, byteorder="little")
    buf += idx.to_bytes(2, byteorder="little")
    buf += crc16.to_bytes(2, byteorder="little")
    buf += send_data
    sum = 0
    for x in buf[1:]:
        sum += x
    sum &= 0xFF
    buf += sum.to_bytes(1, byteorder="little")
    ser.write(buf)


def ChkSumCal(raw: tuple()) -> int:
    chksum = 0
    for i in raw:
        chksum += i
    return chksum % 0x10000


class Response(object):
    def __init__(self, id: int, data: tuple()):
        self.req: int = id
        self.reqData: tuple() = data

    def GetID(self) -> int:
        return self.req

    def GetParam(self) -> tuple():
        return self.reqData


def ChkSumCal(cmd: int, data_size: int, data: tuple()):
    return (cmd + data_size + sum(data, 0)) % 256


def SplSend(ser: serial.Serial, cmd: int, send_data: tuple()):
    buf = SPL_PREAMBLE.to_bytes(1, byteorder="little")
    buf += cmd.to_bytes(1, byteorder="little")
    buf += len(send_data).to_bytes(1, byteorder="little")
    buf += send_data
    buf += ChkSumCal(cmd, len(send_data), send_data).to_bytes(2, byteorder="little")
    ser.write(buf)
    print("Send: [{0}]".format(buf.hex(" ").upper()))


def SplRecv(ser: serial.Serial):
    preamble = int.from_bytes(ser.read(1), byteorder="little")
    if preamble != SPL_PREAMBLE:
        return None
    recv_cmd = int.from_bytes(ser.read(1), byteorder="little")
    recv_size = int.from_bytes(ser.read(1), byteorder="little")
    recv_data = ser.read(recv_size)
    chk_sum = int.from_bytes(ser.read(1), byteorder="little")
    cal_chk_cum = ChkSumCal(recv_cmd, recv_size, recv_data)

    buf = preamble.to_bytes(1, byteorder="little")
    buf += recv_cmd.to_bytes(1, byteorder="little")
    buf += recv_size.to_bytes(1, byteorder="little")
    buf += recv_data
    buf += chk_sum.to_bytes(1, byteorder="little")
    print("Recv: [{0}]".format(buf.hex(" ").upper()))

    if chk_sum == cal_chk_cum:
        return Response(recv_cmd, recv_data)
    return None


def resp_heartbeat(ser: serial.Serial, rsp: Response, dummy=None):
    print("Catch Heartbeat!!!")
    return True


def resp_0xA0(ser: serial.Serial, rsp: Response, dummy=None):
    print("Recv 0xA0 Command!!!")
    return True


def resp_0xA1(ser: serial.Serial, rsp: Response, f: BufferedReader):
    data = f.read(64)
    if len(data) == 0:
        return False
    idx = f.tell() // 64
    data_len = len(data)
    if data_len < 64:
        arr = bytes(64 - data_len)
        data += arr
        idx += 1
    crc = CRC16(data)
    send = int.to_bytes(idx, 2, byteorder="little")
    send += int.to_bytes(crc, 2, byteorder="little")
    send += data
    print("ota packet idx: {0}".format(idx))
    SplSend(ser, 0xA1, send)
    return True


def resp_0xA2(ser: serial.Serial, rsp: Response, dummy=None):
    print("Recv 0xA2 Command!!!")
    return True


responce_cb = {
    0x10: resp_heartbeat,
    0xA0: resp_0xA0,
    0xA1: resp_0xA1,
    0xA2: resp_0xA2,
}


def main(argv):
    ser = serial.Serial(port=argv[1], baudrate=9600, timeout=100.0)
    if ser.isOpen() == False:
        return

    send = int.to_bytes(0, 1, byteorder="little")
    SplSend(ser, 0xA0, send)

    with open(argv[2], "rb") as f:
        f.seek(0, 2)  # move the cursor to the end of the file
        tola_size = f.tell()
        f.seek(0, 0)
        IsKeppAlive = True
        data = f.read(64)
        idx = f.tell() // 64
        crc = CRC16(data)
        send = int.to_bytes(idx, 2, byteorder="little")
        send += int.to_bytes(crc, 2, byteorder="little")
        send += data
        SplSend(ser, 0xA1, send)
        while IsKeppAlive == True:
            rsp = SplRecv(ser)
            if rsp == None:
                IsKeppAlive = False
                print("wait Response timeout.")
            else:
                IsKeppAlive = responce_cb.get(rsp.GetID())(ser, rsp, f)

    with open(argv[2], "rb") as f:
        f.seek(0, 2)  # move the cursor to the end of the file
        tola_size = f.tell()
        f.seek(0, 0)
        data = f.read(tola_size)
        crc = CRC16(data)
        send = int.to_bytes(tola_size, 2, byteorder="little")
        send += int.to_bytes(crc, 2, byteorder="little")
        SplSend(ser, 0xA2, send)
    return


if __name__ == "__main__":
    main(sys.argv)
    input("Press Any Key To Exit...")
