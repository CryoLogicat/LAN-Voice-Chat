$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Invoke-Checked {
	param(
		[Parameter(Mandatory = $true)]
		[string]$Command,
		[Parameter(Mandatory = $true)]
		[string]$Description
	)

	Write-Host "[执行] $Description"
	Invoke-Expression $Command
	if ($LASTEXITCODE -ne 0) {
		throw "失败: $Description (exit=$LASTEXITCODE)"
	}
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
	throw "未检测到 uv，请先安装 uv 后重试。"
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
	Invoke-Checked -Command "uv venv .venv" -Description "创建 .venv 虚拟环境"
}

Invoke-Checked -Command "uv pip install --python `"$VenvPython`" -r requirements.txt pyinstaller" -Description "安装依赖与 PyInstaller"

Invoke-Checked -Command "uv run --python `"$VenvPython`" pyinstaller --noconfirm --onefile --windowed --name LanVoiceChatWindows windows_app.py" -Description "执行 Windows 打包"

$outputExe = Join-Path $ProjectRoot "dist\LanVoiceChatWindows.exe"
if (-not (Test-Path $outputExe)) {
	throw "打包流程结束但未找到输出文件: $outputExe"
}

Write-Host "打包完成，输出文件: $outputExe"
