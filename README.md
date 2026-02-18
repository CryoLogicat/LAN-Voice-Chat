# LAN Voice Chat（局域网语音聊天）

一个面向局域网场景的语音聊天项目，包含：
- Python 中继服务端
- Python 命令行客户端
- Windows 图形化一体端（可开服 + 可入房）
- Android 原生客户端工程（Kotlin）

项目目标是做一个可快速部署、低门槛上手的局域网语音 MVP。

## 功能概览

- 房间模式：同房间内互通语音，不同房间隔离
- 低延迟音频链路：10ms 帧，适合局域网实时通话
- Windows 一体端：同一个界面可启动服务端并加入房间
- Android 客户端：可直接接入同一服务端房间

## 项目结构

```text
.
├─ server.py               # TCP 房间中继服务端
├─ client.py               # 命令行语音客户端
├─ windows_app.py          # Windows GUI 一体端（服务端 + 客户端）
├─ common.py               # 协议与基础收发工具
├─ build_windows.ps1       # Windows 单文件 EXE 打包脚本
├─ requirements.txt
└─ android-client/         # Android Studio 工程
```

## 运行环境

### Python 端（服务端 / CLI 客户端 / Windows GUI）

- Python 3.10+
- 可用麦克风与扬声器
- 建议在同一局域网内测试

安装依赖：

```bash
pip install -r requirements.txt
```

如 `sounddevice` 安装失败，可先升级 pip：

```bash
python -m pip install --upgrade pip
```

### Android 端

- Android Studio（建议最新稳定版）
- 项目配置：`minSdk 26`，`targetSdk 35`
- 运行时需授予麦克风权限（`RECORD_AUDIO`）

## 快速开始（Python 服务端 + 客户端）

### 1) 启动服务端

在局域网可访问机器上运行：

```bash
python server.py --host 0.0.0.0 --port 50000
```

### 2) 启动客户端

在其他设备运行（替换为服务端局域网 IP）：

```bash
python client.py --host 192.168.1.100 --port 50000 --room room1 --name 张三
```

参数说明：
- `--host`：服务端地址（必填）
- `--port`：服务端端口（默认 `50000`）
- `--room`：房间名（必填）
- `--name`：昵称（可选，默认主机名）

客户端内置命令：
- `/mute`：静音麦克风
- `/unmute`：取消静音
- `/quit`：退出

## Windows 图形化一体端

直接运行：

```bash
python windows_app.py
```

界面支持：
- 上半区启动/停止本机服务端
- 下半区作为客户端加入房间
- 一键静音 / 取消静音

## 打包 Windows EXE

执行：

```powershell
./build_windows.ps1
```

说明：
- 打包脚本固定使用 `uv`
- 若没有 `.venv` 会自动创建
- 产物：`dist/LanVoiceChatWindows.exe`

## Android 客户端使用

1. 用 Android Studio 打开 `android-client` 目录
2. 等待 Gradle 同步
3. 运行到真机（建议与服务端在同一局域网）
4. 填写服务端 IP、端口、房间、昵称并连接

## 协议与音频参数

- 传输协议：TCP 自定义包头（`type + payload_size`）
- 消息类型：`JOIN / AUDIO / LEAVE / SYS`
- 音频格式：`16kHz / Mono / 16-bit PCM`
- 帧长：`10ms`

## 当前限制（MVP）

- 暂未实现鉴权与端到端加密
- 暂未实现回声消除（AEC）和噪声抑制
- 网络抖动较大时会出现丢帧或断续

## 常见问题

### 听不到声音

- 检查系统默认输入/输出设备
- 检查服务端机器防火墙端口是否放行

### 有啸叫或回声

- 建议佩戴耳机

### 语音断断续续

- 尽量使用稳定局域网（优先有线）
- 避免 Wi-Fi 高拥塞环境

## 开发建议

- 先用两台设备做基本连通性验证（同房间双向通话）
- 再逐步加特性：鉴权、加密、AEC、统计指标、重连机制

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。


