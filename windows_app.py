import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from client import VoiceClient
from server import VoiceRelayServer


class WindowsVoiceApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LAN Voice Chat - All In One")
        self.root.geometry("620x600")

        self.client: VoiceClient | None = None
        self.connected = False
        self.muted = False
        self.server: VoiceRelayServer | None = None
        self.server_thread: threading.Thread | None = None
        self.server_running = False

        self.server_host_var = tk.StringVar(value="0.0.0.0")
        self.server_port_var = tk.StringVar(value="50000")
        self.host_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="50000")
        self.room_var = tk.StringVar(value="room1")
        self.name_var = tk.StringVar(value=socket.gethostname())

        self._build_ui()
        self._set_state(False)
        self._set_server_state(False)

    def _build_ui(self) -> None:
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        server_frame = ttk.LabelFrame(frm, text="服务端（本机开服）", padding=10)
        server_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        ttk.Label(server_frame, text="监听IP").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(server_frame, textvariable=self.server_host_var, width=24).grid(row=0, column=1, sticky=tk.W, pady=4)
        ttk.Label(server_frame, text="端口").grid(row=0, column=2, sticky=tk.W, padx=(12, 0), pady=4)
        ttk.Entry(server_frame, textvariable=self.server_port_var, width=12).grid(row=0, column=3, sticky=tk.W, pady=4)

        server_btn_bar = ttk.Frame(server_frame)
        server_btn_bar.grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(6, 0))
        self.start_server_btn = ttk.Button(server_btn_bar, text="启动服务端", command=self.start_server)
        self.start_server_btn.pack(side=tk.LEFT)
        self.stop_server_btn = ttk.Button(server_btn_bar, text="停止服务端", command=self.stop_server)
        self.stop_server_btn.pack(side=tk.LEFT, padx=8)
        self.server_status_label = ttk.Label(server_btn_bar, text="状态：未启动")
        self.server_status_label.pack(side=tk.LEFT, padx=(8, 0))

        client_frame = ttk.LabelFrame(frm, text="客户端（加入房间）", padding=10)
        client_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(12, 0))

        ttk.Label(client_frame, text="服务端 IP").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(client_frame, textvariable=self.host_var, width=36).grid(row=0, column=1, sticky=tk.EW, pady=4)

        ttk.Label(client_frame, text="端口").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(client_frame, textvariable=self.port_var, width=36).grid(row=1, column=1, sticky=tk.EW, pady=4)

        ttk.Label(client_frame, text="房间").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Entry(client_frame, textvariable=self.room_var, width=36).grid(row=2, column=1, sticky=tk.EW, pady=4)

        ttk.Label(client_frame, text="昵称").grid(row=3, column=0, sticky=tk.W, pady=4)
        ttk.Entry(client_frame, textvariable=self.name_var, width=36).grid(row=3, column=1, sticky=tk.EW, pady=4)

        btn_bar = ttk.Frame(client_frame)
        btn_bar.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=10)

        self.connect_btn = ttk.Button(btn_bar, text="连接", command=self.connect)
        self.connect_btn.pack(side=tk.LEFT)

        self.mute_btn = ttk.Button(btn_bar, text="静音麦克风", command=self.toggle_mute)
        self.mute_btn.pack(side=tk.LEFT, padx=8)

        self.disconnect_btn = ttk.Button(btn_bar, text="断开", command=self.disconnect)
        self.disconnect_btn.pack(side=tk.LEFT)

        client_frame.columnconfigure(1, weight=1)

        ttk.Label(frm, text="日志").grid(row=2, column=0, sticky=tk.W, pady=(12, 4))
        self.log_text = tk.Text(frm, height=16, wrap=tk.WORD)
        self.log_text.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(3, weight=1)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _append_log(self, text: str) -> None:
        def _ui() -> None:
            self.log_text.insert(tk.END, text + "\n")
            self.log_text.see(tk.END)

        self.root.after(0, _ui)

    def _set_state(self, connected: bool) -> None:
        self.connected = connected
        if connected:
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.mute_btn.config(state=tk.NORMAL)
        else:
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
            self.mute_btn.config(state=tk.DISABLED)
            self.muted = False
            self.mute_btn.config(text="静音麦克风")

    def _set_server_state(self, running: bool) -> None:
        self.server_running = running
        if running:
            self.start_server_btn.config(state=tk.DISABLED)
            self.stop_server_btn.config(state=tk.NORMAL)
            self.server_status_label.config(text="状态：运行中")
        else:
            self.start_server_btn.config(state=tk.NORMAL)
            self.stop_server_btn.config(state=tk.DISABLED)
            self.server_status_label.config(text="状态：未启动")

    def start_server(self) -> None:
        if self.server_running:
            return

        host = self.server_host_var.get().strip() or "0.0.0.0"
        try:
            port = int(self.server_port_var.get().strip())
        except ValueError:
            messagebox.showerror("参数错误", "服务端端口必须是数字")
            return

        self.server = VoiceRelayServer(host=host, port=port)

        def _server_worker() -> None:
            try:
                self.server.start()
            except Exception as exc:
                self._append_log(f"服务端异常: {exc}")
            finally:
                self.root.after(0, lambda: self._set_server_state(False))

        self.server_thread = threading.Thread(target=_server_worker, daemon=True)
        self.server_thread.start()
        self._set_server_state(True)
        self._append_log(f"服务端已启动: {host}:{port}")

    def stop_server(self) -> None:
        if self.server is not None:
            try:
                self.server.stop()
            except Exception:
                pass
            self.server = None
        self._set_server_state(False)
        self._append_log("服务端已停止")

    def connect(self) -> None:
        host = self.host_var.get().strip()
        room = self.room_var.get().strip()
        name = self.name_var.get().strip() or socket.gethostname()

        if not host or not room:
            messagebox.showerror("参数错误", "服务端 IP 与房间不能为空")
            return

        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("参数错误", "端口必须是数字")
            return

        self._append_log("正在连接...")

        def _connect_worker() -> None:
            try:
                self.client = VoiceClient(
                    host=host,
                    port=port,
                    room=room,
                    name=name,
                    on_system_message=self._append_log,
                )
                self.client.start()
                self.root.after(0, lambda: self._set_state(True))
                self._append_log("已连接（低延迟模式）")
            except Exception as exc:
                self._append_log(f"连接失败: {exc}")
                self.root.after(0, lambda: self._set_state(False))

        threading.Thread(target=_connect_worker, daemon=True).start()

    def toggle_mute(self) -> None:
        if not self.client or not self.connected:
            return
        self.muted = not self.muted
        self.client.set_mute(self.muted)
        if self.muted:
            self.mute_btn.config(text="取消静音")
            self._append_log("麦克风已静音")
        else:
            self.mute_btn.config(text="静音麦克风")
            self._append_log("麦克风已开启")

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.stop()
            except Exception:
                pass
            self.client = None
        self._set_state(False)
        self._append_log("已断开")

    def on_close(self) -> None:
        self.disconnect()
        self.stop_server()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = WindowsVoiceApp(root)
    app._append_log("同一 exe 可选择本机开服，或直接作为客户端加入房间")
    root.mainloop()


if __name__ == "__main__":
    main()
