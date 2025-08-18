#!/usr/bin/env python3
"""
简化的FlowSlide启动脚本
解决依赖问题的临时方案
"""

import os
import sys
import warnings

# 添加src到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def check_and_install_dependencies():
    """检查并安装缺失的依赖"""
    required_packages = [
        'prometheus_client',
        'fastapi',
        'uvicorn',
        'pydantic',
        'sqlalchemy',
        'aiosqlite'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} 未安装")
    
    if missing_packages:
        print(f"\n缺失的包: {missing_packages}")
        print("请运行: pip install " + " ".join(missing_packages))
        return False
    
    return True

def start_without_monitoring():
    """启动应用但禁用监控功能"""
    print("🚀 启动FlowSlide (简化模式)")
    
    # 临时禁用监控导入
    import sys
    
    # 创建一个虚拟的监控模块
    class MockMetrics:
        def track_http_request(self, *args, **kwargs):
            pass
        
        def track_user_session(self, *args, **kwargs):
            pass
    
    class MockModule:
        def __init__(self):
            self.metrics_collector = MockMetrics()
        
        def metrics_endpoint(self):
            return {"message": "Monitoring disabled in simple mode"}
    
    # 如果监控模块导入失败，使用mock
    try:
        from flowslide.monitoring import metrics_endpoint, metrics_collector
        print("✅ 监控模块加载成功")
    except ImportError as e:
        print(f"⚠️ 监控模块加载失败: {e}")
        print("🔧 使用简化模式启动...")
        
        # 创建mock模块
        mock_monitoring = MockModule()
        sys.modules['flowslide.monitoring'] = mock_monitoring
        sys.modules['flowslide.monitoring.metrics'] = mock_monitoring
    
    # 现在导入主应用
    try:
        from flowslide.main import app
        print("✅ FlowSlide应用加载成功")
        
        # 启动服务器
        import uvicorn
        print("🌐 启动Web服务器...")
        print("📍 访问地址: http://localhost:8000")
        print("📚 API文档: http://localhost:8000/docs")
        print("🏠 主页: http://localhost:8000/home")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info"
        )
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """主函数"""
    print("🔍 检查依赖...")
    
    # 检查基本依赖
    basic_deps = ['fastapi', 'uvicorn', 'pydantic', 'sqlalchemy']
    missing_basic = []
    
    for dep in basic_deps:
        try:
            __import__(dep)
        except ImportError:
            missing_basic.append(dep)
    
    if missing_basic:
        print(f"❌ 缺失基本依赖: {missing_basic}")
        print("请先安装基本依赖:")
        print(f"pip install {' '.join(missing_basic)}")
        sys.exit(1)
    
    # 启动应用
    try:
        start_without_monitoring()
    except KeyboardInterrupt:
        print("\n👋 FlowSlide已停止")
    except Exception as e:
        print(f"💥 启动异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
