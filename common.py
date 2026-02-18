import json
import socket
import struct
from typing import Optional, Tuple

MSG_JOIN = 1
MSG_AUDIO = 2
MSG_LEAVE = 3
MSG_SYS = 4

_HEADER_STRUCT = struct.Struct("!BI")


def send_packet(sock: socket.socket, msg_type: int, payload: bytes = b"") -> None:
    header = _HEADER_STRUCT.pack(msg_type, len(payload))
    sock.sendall(header + payload)


def recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def recv_packet(sock: socket.socket) -> Optional[Tuple[int, bytes]]:
    header = recv_exact(sock, _HEADER_STRUCT.size)
    if header is None:
        return None
    msg_type, size = _HEADER_STRUCT.unpack(header)
    payload = recv_exact(sock, size)
    if payload is None:
        return None
    return msg_type, payload


def pack_json(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def unpack_json(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))
