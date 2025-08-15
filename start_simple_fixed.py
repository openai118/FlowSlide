#!/usr/bin/env python3
"""
FlowSlide 简化启动脚本 - 带环境检测
"""

#!/usr/bin/env python3
"""
FlowSlide 简化启动脚本 - 带环境检测
"""

import os
import sys
from pathlib import Path


def setup_environment():
    """设置环境变量和路径"""
    # 获取项目根目录
    project_root = Path(__file__).parent
    os.chdir(project_root)

    # 添加src目录到Python路径
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # 设置环境变量
    os.environ.setdefault("DATABASE_URL", "sqlite:///./data/flowslide.db")
    os.environ.setdefault("PORT", "8000")
    os.environ.setdefault("DEBUG", "True")

    # 确保数据目录存在
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)

    print(f"✅ 工作目录: {project_root}")
    print(f"✅ Python路径: {src_path}")
    print(f"✅ 数据库: {os.environ['DATABASE_URL']}")
    print(f"✅ 端口: {os.environ['PORT']}")


def main():
    """主启动函数"""
    print("🚀 FlowSlide 启动中...")

    try:
        # 1. 环境设置
        setup_environment()

        # 2. 导入检查
        print("\n📦 检查导入...")
        try:
            import uvicorn
            print("✅ uvicorn")
        except ImportError as e:
            print(f"❌ uvicorn: {e}")
            print("💡 尝试安装: pip install uvicorn")
            return

        try:
            from flowslide.main import app
            print("✅ flowslide.main")
        except ImportError as e:
            print(f"❌ flowslide.main: {e}")
            return

        # 3. 启动服务器
        print("\n🌐 启动 FlowSlide 服务器...")
        print("📍 地址: http://127.0.0.1:8000")
        print("🏠 首页(公共): http://127.0.0.1:8000/home")
        print("📚 API文档: http://127.0.0.1:8000/docs")
        print("🎯 Web界面(控制台): http://127.0.0.1:8000/web")
        print("\n按 Ctrl+C 停止服务器")

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            access_log=True,
        )

    except KeyboardInterrupt:
        print("\n👋 FlowSlide 已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
