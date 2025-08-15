echo "开始测试FlowSlide..."
echo "当前目录: $PWD"
echo "Python版本:"
python --version
echo "激活虚拟环境..."
source .venv/Scripts/activate 2>/dev/null || .venv\Scripts\activate.bat
echo "Python路径:"
which python || where python
echo "尝试启动服务器..."
python start_flowslide.py
