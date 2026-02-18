import argparse
import queue
import socket
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from common import MSG_AUDIO, MSG_JOIN, MSG_LEAVE, MSG_SYS, pack_json, recv_packet, send_packet, unpack_json

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
FRAME_MS = 10
BLOCK_SIZE = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = BLOCK_SIZE * 2
MIC_QUEUE_MAX = 8
PLAY_QUEUE_MAX = 10
MAX_JITTER_FRAMES = 2


class VoiceClient:
    def __init__(
        self,
        host: str,
        port: int,
        room: str,
        name: str,
        on_system_message: Optional[Callable[[str], None]] = None,
    ):
        self.host = host
        self.port = port
        self.room = room
        self.name = name
        self.on_system_message = on_system_message

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.running = threading.Event()
        self.running.clear()
        self.connected = False

        self.capture_enabled = True
        self.capture_lock = threading.Lock()

        self.mic_queue: queue.Queue[bytes] = queue.Queue(maxsize=MIC_QUEUE_MAX)
        self.play_queue: queue.Queue[bytes] = queue.Queue(maxsize=PLAY_QUEUE_MAX)
        self.sender_thread: Optional[threading.Thread] = None
        self.receiver_thread: Optional[threading.Thread] = None
        self.input_stream: Optional[sd.InputStream] = None
        self.output_stream: Optional[sd.OutputStream] = None

    def _emit_system(self, text: str) -> None:
        if self.on_system_message is not None:
            self.on_system_message(text)
        else:
            print(f"[系统] {text}")

    @staticmethod
    def _put_latest_frame(target_queue: queue.Queue[bytes], frame: bytes) -> None:
        try:
            target_queue.put_nowait(frame)
            return
        except queue.Full:
            pass

        try:
            target_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            target_queue.put_nowait(frame)
        except queue.Full:
            pass

    def connect(self) -> None:
        target_host = self.host
        if self.host in {"0.0.0.0", "::"}:
            target_host = "127.0.0.1"
            self._emit_system("客户端不能连接 0.0.0.0，已自动改为 127.0.0.1")

        try:
            self.sock.connect((target_host, self.port))
        except OSError as exc:
            raise RuntimeError(
                f"连接失败: {target_host}:{self.port}。请确认服务端已启动，且端口/IP 正确。"
            ) from exc

        send_packet(self.sock, MSG_JOIN, pack_json({"room": self.room, "name": self.name}))
        self.connected = True

    def _send_loop(self) -> None:
        while self.running.is_set():
            try:
                frame = self.mic_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                send_packet(self.sock, MSG_AUDIO, frame)
            except OSError:
                self.running.clear()
                break

    def _recv_loop(self) -> None:
        while self.running.is_set():
            try:
                packet = recv_packet(self.sock)
            except OSError:
                self.running.clear()
                break
            if packet is None:
                self.running.clear()
                break
            msg_type, payload = packet
            if msg_type == MSG_AUDIO:
                if len(payload) == FRAME_BYTES:
                    self._put_latest_frame(self.play_queue, payload)
            elif msg_type == MSG_SYS:
                try:
                    text = unpack_json(payload).get("text", "")
                except Exception:
                    text = payload.decode("utf-8", errors="ignore")
                self._emit_system(text)

    def _input_callback(self, indata, frames, time_info, status) -> None:
        if not self.running.is_set():
            return
        if status:
            return
        with self.capture_lock:
            if not self.capture_enabled:
                return
        frame = np.asarray(indata, dtype=np.int16).reshape(-1).tobytes()
        if len(frame) != FRAME_BYTES:
            return
        self._put_latest_frame(self.mic_queue, frame)

    def _output_callback(self, outdata, frames, time_info, status) -> None:
        if not self.running.is_set():
            outdata[:] = np.zeros((frames, CHANNELS), dtype=np.int16)
            return

        while self.play_queue.qsize() > MAX_JITTER_FRAMES + 1:
            try:
                self.play_queue.get_nowait()
            except queue.Empty:
                break

        try:
            frame = self.play_queue.get_nowait()
            arr = np.frombuffer(frame, dtype=np.int16).reshape(-1, CHANNELS)
            if arr.shape[0] == frames:
                outdata[:] = arr
            else:
                outdata[:] = np.zeros((frames, CHANNELS), dtype=np.int16)
        except queue.Empty:
            outdata[:] = np.zeros((frames, CHANNELS), dtype=np.int16)

    def run(self) -> None:
        self.start()
        self._emit_system("已连接（低延迟模式）。命令：/mute 静音麦克风，/unmute 取消静音，/quit 退出")

        try:
            while self.running.is_set():
                cmd = input().strip().lower()
                if cmd == "/quit":
                    break
                if cmd == "/mute":
                    self.set_mute(True)
                    print("麦克风已静音")
                elif cmd == "/unmute":
                    self.set_mute(False)
                    print("麦克风已开启")
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            self.stop()

    def start(self) -> None:
        if self.running.is_set():
            return

        self.connect()
        self.running.set()

        self.sender_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.receiver_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.sender_thread.start()
        self.receiver_thread.start()

        self.input_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCK_SIZE,
            latency="low",
            callback=self._input_callback,
        )
        self.output_stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCK_SIZE,
            latency="low",
            callback=self._output_callback,
        )
        self.input_stream.start()
        self.output_stream.start()

    def stop(self) -> None:
        self.running.clear()

        try:
            if self.connected:
                send_packet(self.sock, MSG_LEAVE)
        except OSError:
            pass

        for stream in (self.input_stream, self.output_stream):
            if stream is not None:
                try:
                    stream.stop()
                except Exception:
                    pass
                try:
                    stream.close()
                except Exception:
                    pass

        self.input_stream = None
        self.output_stream = None

        time.sleep(0.05)
        try:
            self.sock.close()
        except OSError:
            pass

        self.connected = False

    def set_mute(self, muted: bool) -> None:
        with self.capture_lock:
            self.capture_enabled = not muted

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LAN Voice Chat Client")
    parser.add_argument("--host", required=True, help="Server IP address")
    parser.add_argument("--port", type=int, default=50000, help="Server port, default 50000")
    parser.add_argument("--room", required=True, help="Room name")
    parser.add_argument("--name", default="", help="Display name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    name = args.name.strip() or socket.gethostname()
    client = VoiceClient(args.host, args.port, args.room, name)
    try:
        client.run()
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
