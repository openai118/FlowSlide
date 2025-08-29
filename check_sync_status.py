#!/usr/bin/env python3
"""
检查同步状态
"""

import asyncio
import sys
sys.path.append('src')

async def check_sync_status():
    try:
        from flowslide.database.database import initialize_database
        from flowslide.services.data_sync_service import get_sync_status

        # 确保数据库管理器已初始化
        db_mgr = initialize_database()
        print('=== 数据库状态 ===')
        print(f'数据库类型: {db_mgr.database_type}')
        print(f'同步启用: {db_mgr.sync_enabled}')
        external_status = '已连接' if db_mgr.external_engine else '未连接'
        print(f'外部引擎: {external_status}')
        print(f'外部URL: {db_mgr.external_url}')

        status = await get_sync_status()
        print('\n=== 同步状态 ===')
        print(f'同步启用: {status["enabled"]}')
        print(f'同步运行中: {status["running"]}')
        print(f'最后同步: {status["last_sync"]}')
        print(f'同步模式: {status["mode"]}')
        print(f'同步间隔: {status["interval"]}秒')
        print(f'同步方向: {status["directions"]}')
        print(f'外部数据库类型: {status["external_db_type"]}')
        print(f'外部数据库配置: {status["external_db_configured"]}')

    except Exception as e:
        print(f'检查失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_sync_status())
