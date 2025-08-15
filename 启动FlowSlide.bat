@echo off
title FlowSlide Server
echo.
echo 🚀 正在启动FlowSlide服务器...
echo.

cd /d "%~dp0"

echo 📁 当前目录: %CD%
echo.

echo 🐍 激活虚拟环境...
call .venv\Scripts\activate.bat

echo.
echo 🧪 使用本地SQLite数据库配置...
set DATABASE_URL=sqlite:///./data/flowslide.db
set PORT=8000

echo.
echo 🚀 启动FlowSlide服务器...
echo 📍 访问地址: http://localhost:8000
echo 🏠 首页(公共): http://localhost:8000/home
echo 📚 API文档: http://localhost:8000/docs
echo 🌐 Web界面(控制台): http://localhost:8000/web
echo ⚙️ 配置页面: http://localhost:8000/web/ai-config
echo.
echo 按 Ctrl+C 停止服务器
echo ==========================================
echo.

python start_flowslide.py

echo.
echo 服务器已停止
pause
