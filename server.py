import argparse
import socket
import threading
from dataclasses import dataclass
from typing import Dict, Set

from common import MSG_AUDIO, MSG_JOIN, MSG_LEAVE, MSG_SYS, pack_json, recv_packet, send_packet, unpack_json


@dataclass(eq=False)
class ClientConn:
    sock: socket.socket
    addr: tuple
    name: str = ""
    room: str = ""


class VoiceRelayServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server_sock: socket.socket | None = None
        self.rooms: Dict[str, Set[ClientConn]] = {}
        self.rooms_lock = threading.Lock()
        self.running = threading.Event()

    def start(self) -> None:
        self.running.set()
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(100)
        self.server_sock.settimeout(1.0)
        print(f"[SERVER] listening on {self.host}:{self.port}")

        while self.running.is_set():
            try:
                client_sock, addr = self.server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                if self.running.is_set():
                    raise
                break
            client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(target=self.handle_client, args=(client_sock, addr), daemon=True).start()

    def stop(self) -> None:
        self.running.clear()
        sock = self.server_sock
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
            self.server_sock = None

    def _broadcast_sys(self, room: str, text: str, exclude: ClientConn | None = None) -> None:
        payload = pack_json({"text": text})
        with self.rooms_lock:
            clients = list(self.rooms.get(room, set()))
        for c in clients:
            if exclude is not None and c is exclude:
                continue
            try:
                send_packet(c.sock, MSG_SYS, payload)
            except OSError:
                pass

    def _remove_client(self, client: ClientConn) -> None:
        removed = False
        with self.rooms_lock:
            if client.room in self.rooms and client in self.rooms[client.room]:
                self.rooms[client.room].remove(client)
                removed = True
                if not self.rooms[client.room]:
                    del self.rooms[client.room]
        if removed:
            self._broadcast_sys(client.room, f"{client.name} 离开房间")

    def _forward_audio(self, sender: ClientConn, audio_payload: bytes) -> None:
        with self.rooms_lock:
            peers = list(self.rooms.get(sender.room, set()))
        for peer in peers:
            if peer is sender:
                continue
            try:
                send_packet(peer.sock, MSG_AUDIO, audio_payload)
            except OSError:
                pass

    def handle_client(self, client_sock: socket.socket, addr: tuple) -> None:
        client = ClientConn(sock=client_sock, addr=addr)
        try:
            first = recv_packet(client_sock)
            if first is None:
                client_sock.close()
                return

            msg_type, payload = first
            if msg_type != MSG_JOIN:
                send_packet(client_sock, MSG_SYS, pack_json({"text": "first packet must be JOIN"}))
                client_sock.close()
                return

            info = unpack_json(payload)
            room = str(info.get("room", "")).strip()
            name = str(info.get("name", "")).strip() or f"{addr[0]}:{addr[1]}"
            if not room:
                send_packet(client_sock, MSG_SYS, pack_json({"text": "room is required"}))
                client_sock.close()
                return

            client.room = room
            client.name = name

            with self.rooms_lock:
                self.rooms.setdefault(room, set()).add(client)

            send_packet(client_sock, MSG_SYS, pack_json({"text": f"已加入房间 {room}"}))
            self._broadcast_sys(room, f"{name} 加入房间", exclude=client)
            print(f"[JOIN] {name} @ {addr} room={room}")

            while True:
                packet = recv_packet(client_sock)
                if packet is None:
                    break
                t, p = packet
                if t == MSG_AUDIO:
                    self._forward_audio(client, p)
                elif t == MSG_LEAVE:
                    break

        except (ConnectionResetError, OSError):
            pass
        finally:
            self._remove_client(client)
            try:
                client_sock.close()
            except OSError:
                pass
            if client.name:
                print(f"[LEAVE] {client.name} @ {addr}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LAN Voice Relay Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host, default 0.0.0.0")
    parser.add_argument("--port", type=int, default=50000, help="Bind port, default 50000")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = VoiceRelayServer(args.host, args.port)
    server.start()


if __name__ == "__main__":
    main()
