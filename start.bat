@echo off
echo 🚀 启动FlowSlide应用...

REM 激活虚拟环境
call .venv\Scripts\activate.bat

REM 启动应用
python -m uvicorn src.flowslide.main:app --host 0.0.0.0 --port 8000 --reload

pause
