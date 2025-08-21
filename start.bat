@echo off
echo 🚀 启动FlowSlide应用...
echo.

REM 检查虚拟环境是否存在
if not exist ".venv\Scripts\python.exe" (
    echo ❌ 虚拟环境不存在，请先运行: python -m venv .venv
    echo    然后安装依赖: uv sync
    pause
    exit /b 1
)

echo ✅ 使用虚拟环境: .venv\Scripts\python.exe
echo 📍 访问地址: http://localhost:8000
echo 🏠 主页: http://localhost:8000/home
echo 📚 API文档: http://localhost:8000/docs
echo.

REM 直接使用虚拟环境的Python启动应用
.venv\Scripts\python.exe -m uvicorn src.flowslide.main:app --host 0.0.0.0 --port 8000 --reload

pause
