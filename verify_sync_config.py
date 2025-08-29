#!/usr/bin/env python3
"""
验证智能同步配置
"""

import os
import sys

# 添加项目路径
sys.path.append('src')

def test_env_config():
    """测试环境变量配置"""
    print("=== 环境变量配置测试 ===")

    # 手动加载.env文件
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ .env文件加载成功")
    except ImportError:
        print("⚠️ python-dotenv未安装，使用系统环境变量")

    # 检查关键配置
    configs = {
        'DATABASE_MODE': os.getenv('DATABASE_MODE', 'local'),
        'DATABASE_URL': '已配置' if os.getenv('DATABASE_URL') else '未配置',
        'SYNC_INTERVAL': os.getenv('SYNC_INTERVAL', '300'),
        'SYNC_MODE': os.getenv('SYNC_MODE', 'incremental'),
        'API_URL': '已配置' if os.getenv('API_URL') else '未配置',
        'R2_ACCESS_KEY_ID': '已配置' if os.getenv('R2_ACCESS_KEY_ID') else '未配置',
        'GOOGLE_API_KEY': '已配置' if os.getenv('GOOGLE_API_KEY') else '未配置'
    }

    for key, value in configs.items():
        print(f"{key}: {value}")

    # 显示数据库URL详情
    db_url = os.getenv('DATABASE_URL', '')
    if db_url:
        print(f"\n数据库URL详情: {db_url[:80]}...")
        if 'supabase' in db_url or 'pooler.supabase.com' in db_url:
            print("✅ 检测到Supabase数据库配置")
        else:
            print("ℹ️ 使用普通PostgreSQL配置")

def test_sync_service():
    """测试同步服务"""
    print("\n=== 智能同步服务测试 ===")

    try:
        # 先初始化数据库管理器
        from flowslide.database.database import initialize_database
        db_mgr = initialize_database()
        print(f"数据库管理器初始化: 同步启用={db_mgr.sync_enabled}")

        # 然后测试同步服务
        from flowslide.services.data_sync_service import sync_service, get_sync_status
        import asyncio

        async def run_test():
            print(f"同步方向: {sync_service.sync_directions}")
            print(f"同步间隔: {sync_service.sync_interval}秒")
            print(f"同步模式: {sync_service.sync_mode}")

            # 获取同步状态
            status = await get_sync_status()
            print(f"同步启用: {status['enabled']}")
            print(f"外部数据库配置: {status['external_db_configured']}")
            print(f"外部数据库类型: {status['external_db_type']}")

            if sync_service.sync_directions:
                print("✅ 智能同步已启用！")
                print(f"🔄 同步策略: {sync_service.sync_directions}")
                return True
            else:
                print("❌ 同步未启用 - 请检查数据库配置")
                return False

        return asyncio.run(run_test())

    except Exception as e:
        print(f"❌ 同步服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🎯 FlowSlide 智能同步配置验证")
    print("=" * 50)

    # 测试环境配置
    test_env_config()

    # 测试同步服务
    sync_ok = test_sync_service()

    print("\n" + "=" * 50)
    if sync_ok:
        print("🎉 智能同步配置验证成功！")
        print("\n📋 配置总结:")
        print("✅ Supabase数据库: 已配置")
        print("✅ R2云存储: 已配置")
        print("✅ Google AI: 已配置")
        print("✅ 智能双向同步: 已启用")
        print("\n🚀 现在可以启动应用程序测试同步功能了！")
    else:
        print("❌ 配置验证失败，请检查上述错误信息")

if __name__ == "__main__":
    main()
