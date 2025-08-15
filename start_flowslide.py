"""
FlowSlide启动器 - 修复版本
"""

import sys
import os
import logging

# 设置工作目录为项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)
print(f"🏠 工作目录: {os.getcwd()}")

# 优先加载本地开发配置
from dotenv import load_dotenv
if os.path.exists('.env.local'):
    print("📄 加载本地开发配置 (.env.local)")
    load_dotenv('.env.local', override=True)
else:
    print("📄 加载默认配置 (.env)")
    load_dotenv()

# 添加src到Python路径
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
print(f"📁 Python路径已添加: {src_path}")

# 设置日志
logging.basicConfig(level=logging.INFO)

try:
    print("🔍 导入FlowSlide模块...")
    from flowslide.main import app
    print("✅ 导入成功!")
    
    # 启动服务器
    import uvicorn
    print("🚀 启动FlowSlide服务器...")
    print("📍 访问地址: http://localhost:8000")
    print("🏠 首页(公共): http://localhost:8000/home")
    print("📚 API文档: http://localhost:8000/docs")
    print("🌐 Web界面(控制台): http://localhost:8000/web")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
    
except Exception as e:
    print(f"❌ 启动失败: {e}")
    import traceback
    traceback.print_exc()
    input("按Enter键退出...")
