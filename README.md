# 局域网语音联机（MVP）

这是一个最小可用的局域网语音聊天程序，包含：
- `server.py`：房间中继服务器
- `client.py`：命令行语音客户端
- `windows_app.py`：Windows 图形化一体端（可开服 + 可入房）
- `android-client/`：Android 原生客户端工程（Android Studio）

## 1. 环境要求

- Windows / macOS / Linux
- Python 3.10+
- 可用麦克风和扬声器

## 2. 安装依赖

在项目目录执行：

```bash
pip install -r requirements.txt
```

> 如果 `sounddevice` 安装失败，Windows 上可先升级 pip：
> `python -m pip install --upgrade pip`

## 3. 启动服务端

在一台局域网可访问的机器上运行：

```bash
python server.py --host 0.0.0.0 --port 50000
```

## 4. 启动客户端

每个成员在自己的机器运行（把 `192.168.1.100` 换成服务端局域网 IP）：

```bash
python client.py --host 192.168.1.100 --port 50000 --room room1 --name 张三
```

- `--room`：房间名，相同房间可以互通语音
- `--name`：昵称，不填则使用主机名

## 5. 客户端命令

连接后可输入：
- `/mute`：静音麦克风（只听不说）
- `/unmute`：取消静音
- `/quit`：退出

## 6. Windows 图形化 APP

运行桌面版：

```bash
python windows_app.py
```

这个界面里可同时做两件事：
- 启动/停止本机服务端（上半区）
- 作为客户端连接房间语音（下半区）

打包为 exe：

```powershell
./build_windows.ps1
```

说明：
- 打包脚本已固定使用 `uv`（不会调用 `pip`）。
- 若本地没有 `.venv`，脚本会自动执行 `uv venv .venv`。
- 请确保已安装 `uv` 并在 PATH 中可用。

打包结果：`dist/LanVoiceChatWindows.exe`

`LanVoiceChatWindows.exe` 为单文件一体端：同一个 exe 内置服务端与客户端能力。

## 7. Android APP（原生工程）

目录：`android-client/`

使用方法：
1. 用 Android Studio 打开 `android-client` 目录。
2. 等待 Gradle 同步完成。
3. 连接真机（建议同一局域网），运行 App。
4. 在 App 里填服务端 IP（例如 `192.168.1.100`）、端口 `50000`、房间和昵称后连接。

注意：
- 需要授予麦克风权限。
- 手机和服务端必须在同一局域网，且服务端端口已放行。

## 8. 说明

- 传输格式：16kHz / 单声道 / 16-bit PCM
- 当前实现是服务端中继转发，适合局域网内低延迟语音（10ms 帧）
- 这是 MVP 版本，未做加密、鉴权、AEC（回声消除）等高级能力

## 9. 常见问题

1. **听不到声音**
   - 检查麦克风/扬声器是否被系统占用
   - 检查防火墙是否放行服务端端口

2. **有啸叫/回声**
   - 建议佩戴耳机

3. **断断续续**
   - 局域网拥塞时会丢帧；可优先使用有线网络

## 10. 开源发布到 GitHub

本项目已按开源仓库方式整理：
- 使用 MIT 许可证（见 `LICENSE`）
- 根目录 `.gitignore` 已忽略虚拟环境、打包产物、Android 构建目录与本地配置

首次发布建议流程：

1. 在 GitHub 网页新建空仓库（不要勾选 README / .gitignore / LICENSE）。
2. 在本地项目目录执行：

```bash
git init
git add .
git commit -m "chore: initial open-source release"
git branch -M main
git remote add origin <你的仓库地址>
git push -u origin main
```

示例仓库地址：
- HTTPS：`https://github.com/<username>/lan-voice-chat.git`
- SSH：`git@github.com:<username>/lan-voice-chat.git`

