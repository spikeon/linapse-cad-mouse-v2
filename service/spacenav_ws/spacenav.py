import asyncio
import logging
import socket
import struct
from dataclasses import dataclass
from typing import List

SPACENAV_SOCKET_PATH = "/var/run/spnav.sock"


def get_sync_spacenav_socket():
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SPACENAV_SOCKET_PATH)
    return sock


async def get_async_spacenav_socket_reader() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    try:
        return await asyncio.open_unix_connection(SPACENAV_SOCKET_PATH)
    except (FileNotFoundError, ConnectionRefusedError):
        logging.exception("Space mouse not found!")
        exit(1)


@dataclass
class MotionEvent:
    x: int
    y: int
    z: int
    pitch: int
    yaw: int
    roll: int
    period: int
    type: str = "mtn"


@dataclass
class ButtonEvent:
    button_id: int
    pressed: bool
    type: str = "btn"


def from_message(message: List[int]) -> MotionEvent | ButtonEvent:
    if message[0] == 0:
        return MotionEvent(x=message[1], z=message[2], y=message[3], pitch=message[4], yaw=message[5], roll=message[6], period=message[7])
    return ButtonEvent(button_id=message[1], pressed=True if message[0] == 1 else False)


if __name__ == "__main__":
    sock = get_sync_spacenav_socket()
    while True:
        chunk = sock.recv(32)
        nums = struct.unpack("iiiiiiii", chunk)
        print(from_message(list(nums)))
