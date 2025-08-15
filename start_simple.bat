@echo off
echo 正在启动 FlowSlide...
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python simple_test.py
pause
