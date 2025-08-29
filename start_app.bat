@echo off
echo 🚀 启动 FlowSlide 应用程序...
echo.

cd /d %~dp0

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请确保已安装Python 3.11+
    pause
    exit /b 1
)

REM 启动应用程序
echo 📦 正在启动 FlowSlide...
python -m src.flowslide.main

pause
