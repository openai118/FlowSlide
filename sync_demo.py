#!/usr/bin/env python3
"""
智能双向同步功能演示
展示本地SQLite与Supabase PostgreSQL之间的双向同步
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append('src')

async def demonstrate_sync():
    """演示同步功能"""
    print("🎯 FlowSlide 智能双向同步演示")
    print("=" * 60)

    try:
        # 初始化数据库管理器
        from flowslide.database.database import initialize_database
        db_mgr = initialize_database()
        print("✅ 数据库管理器初始化成功")
        print(f"   数据库类型: {db_mgr.database_type}")
        print(f"   同步启用: {db_mgr.sync_enabled}")
        print(f"   外部引擎: {'已连接' if db_mgr.external_engine else '未连接'}")

        # 初始化同步服务
        from flowslide.services.data_sync_service import sync_service, get_sync_status, trigger_manual_sync
        print("\n✅ 同步服务初始化成功")
        print(f"   同步方向: {sync_service.sync_directions}")
        print(f"   同步间隔: {sync_service.sync_interval}秒")
        print(f"   同步模式: {sync_service.sync_mode}")

        # 获取同步状态
        status = await get_sync_status()
        print("\n📊 当前同步状态:")
        print(f"   同步启用: {status['enabled']}")
        print(f"   同步运行中: {status['running']}")
        print(f"   最后同步: {status['last_sync'] or '从未同步'}")
        print(f"   外部数据库配置: {status['external_db_configured']}")
        print(f"   外部数据库类型: {status['external_db_type']}")

        # 演示手动同步
        print("\n🔄 执行手动同步...")
        sync_result = await trigger_manual_sync()
        print(f"   同步结果: {sync_result['status']}")
        print(f"   消息: {sync_result['message']}")

        # 显示同步功能说明
        print("\n📋 智能双向同步功能说明:")
        print("1. 🔄 自动同步: 每5分钟自动执行增量同步")
        print("2. 📤 本地 → 外部: 新建用户自动同步到Supabase")
        print("3. 📥 外部 → 本地: Supabase用户同步到本地SQLite")
        print("4. 🔍 冲突解决: 智能处理重复用户和数据冲突")
        print("5. 📊 状态监控: 通过API实时查看同步状态")

        print("\n🚀 同步功能已完全就绪！")
        print("   • 本地SQLite数据库: 快速访问")
        print("   • Supabase PostgreSQL: 云端备份")
        print("   • 双向自动同步: 数据一致性保证")

        return True

    except Exception as e:
        print(f"❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_api_endpoints():
    """显示同步相关API端点"""
    print("\n🔗 同步管理API端点:")
    print("   GET  /api/database/sync/status   - 获取同步状态")
    print("   POST /api/database/sync/trigger  - 手动触发同步")
    print("   GET  /api/database/sync/config   - 获取同步配置")

def show_usage_scenarios():
    """显示使用场景"""
    print("\n🎭 使用场景:")
    print("   1. 多设备同步: 在不同设备间同步用户数据")
    print("   2. 云端备份: 自动备份本地数据到Supabase")
    print("   3. 离线工作: 本地SQLite保证离线可用性")
    print("   4. 团队协作: 共享用户数据到云端数据库")

def main():
    """主函数"""
    success = asyncio.run(demonstrate_sync())

    if success:
        show_api_endpoints()
        show_usage_scenarios()

        print("\n" + "=" * 60)
        print("🎉 智能双向同步演示完成！")
        print("\n💡 提示:")
        print("   • 启动应用程序: python -m src.flowslide.main")
        print("   • 访问Web界面: http://localhost:8000")
        print("   • 查看同步状态: http://localhost:8000/api/database/sync/status")
    else:
        print("\n❌ 演示失败，请检查配置和错误信息")

if __name__ == "__main__":
    main()
