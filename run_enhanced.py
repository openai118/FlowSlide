#!/usr/bin/env python3
"""
LandPPT 增强版应用启动器
集成了数据库监控和系统健康检查功能
"""

import uvicorn
import sys
import os
import asyncio
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Load environment variables with error handling
try:
    load_dotenv()
except PermissionError as e:
    print(f"Warning: Could not load .env file due to permission error: {e}")
    print("Continuing with system environment variables...")
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")
    print("Continuing with system environment variables...")

def run_database_health_check():
    """运行数据库健康检查"""
    print("🔍 Running database health check...")
    
    # 检查是否配置了数据库
    if not os.getenv("DB_HOST"):
        print("ℹ️  No database configuration found, skipping health check")
        return True
    
    # 检查健康检查工具是否存在
    health_check_script = Path("quick_db_check.py")
    if not health_check_script.exists():
        print("⚠️  Database health check tool not found, skipping")
        return True
    
    try:
        # 运行快速数据库检查
        result = subprocess.run([
            sys.executable, str(health_check_script)
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Database health check passed")
            return True
        else:
            print("⚠️  Database health check warnings:")
            print(result.stdout[-500:] if result.stdout else "No output")
            if result.stderr:
                print("Errors:", result.stderr[-500:])
            
            # 检查是否要求数据库连接
            require_db = os.getenv("REQUIRE_DB", "false").lower() == "true"
            if require_db:
                print("❌ Database connection required but health check failed")
                return False
            else:
                print("ℹ️  Database issues detected but not required, continuing...")
                return True
    
    except subprocess.TimeoutExpired:
        print("⚠️  Database health check timed out")
        return not os.getenv("REQUIRE_DB", "false").lower() == "true"
    except Exception as e:
        print(f"⚠️  Database health check error: {e}")
        return not os.getenv("REQUIRE_DB", "false").lower() == "true"

def setup_directories():
    """创建必要的目录"""
    directories = [
        "temp/ai_responses_cache",
        "temp/style_genes_cache", 
        "temp/summeryanyfile_cache",
        "temp/templates_cache",
        "research_reports",
        "uploads",
        "data",
        "logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

def print_startup_info():
    """打印启动信息"""
    print("=" * 60)
    print("🎯 LandPPT - AI驱动的PPT生成平台")
    print("   增强版 - 集成数据库监控和备份功能")
    print("=" * 60)
    
    # 显示配置信息
    features = []
    
    if os.getenv("DB_HOST"):
        features.append("✅ 数据库监控")
    else:
        features.append("⚪ 数据库监控 (未配置)")
    
    if os.getenv("R2_ACCESS_KEY_ID"):
        features.append("✅ R2 备份")
    else:
        features.append("⚪ R2 备份 (未配置)")
    
    if os.getenv("OPENAI_API_KEY"):
        features.append("✅ OpenAI")
    else:
        features.append("⚪ OpenAI (未配置)")
    
    if os.getenv("TAVILY_API_KEY"):
        features.append("✅ 研究功能")
    else:
        features.append("⚪ 研究功能 (未配置)")
    
    print("🔧 功能状态:")
    for feature in features:
        print(f"   {feature}")
    
    print()

def main():
    """主启动函数"""
    
    # 打印启动信息
    print_startup_info()
    
    # 创建必要目录
    print("📁 Setting up directories...")
    setup_directories()
    
    # 运行数据库健康检查
    if not run_database_health_check():
        print("❌ Database health check failed and database is required")
        print("   Please check your database configuration and try again")
        sys.exit(1)
    
    # 获取配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() in ("true", "1", "yes", "on")
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    # 开发模式检查
    if reload and os.getenv("DEV_RELOAD", "false").lower() == "true":
        print("🔄 Development mode enabled - auto-reload on")
    elif reload:
        print("⚠️  Reload mode disabled in production")
        reload = False
    
    # 服务器配置
    config = {
        "app": "landppt.main:app",
        "host": host,
        "port": port,
        "reload": reload,
        "log_level": log_level,
        "access_log": True,
    }
    
    print("🚀 Starting LandPPT Server...")
    print(f"📍 Host: {config['host']}")
    print(f"🔌 Port: {config['port']}")
    print(f"🔄 Reload: {config['reload']}")
    print(f"📊 Log Level: {config['log_level']}")
    print(f"📍 Server: http://localhost:{config['port']}")
    print(f"📚 API Docs: http://localhost:{config['port']}/docs")
    print(f"🌐 Web UI: http://localhost:{config['port']}/web")
    
    # 显示管理工具信息
    print()
    print("🛠️  管理工具:")
    print(f"   数据库检查: python quick_db_check.py")
    print(f"   系统验证: python validate_system.py")
    if os.getenv("R2_ACCESS_KEY_ID"):
        print(f"   备份管理: ./backup-manager.sh status")
    print("=" * 60)
    
    try:
        uvicorn.run(**config)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
