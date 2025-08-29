#!/usr/bin/env python3
"""
手动触发同步
"""

import asyncio
import sys
sys.path.append('src')

async def manual_sync():
    try:
        from flowslide.services.data_sync_service import DataSyncService

        print('=== 手动触发同步 ===')

        # 创建同步服务实例
        sync_service = DataSyncService()

        print(f'同步方向: {sync_service.sync_directions}')
        print(f'同步模式: {sync_service.sync_mode}')
        print(f'最后同步时间: {sync_service.last_sync_time}')

        # 手动触发同步
        print('\n开始同步...')
        await sync_service.sync_data()

        print('同步完成！')

        # 再次检查数据库状态
        from flowslide.database.database import initialize_database
        db_mgr = initialize_database()

        print('\n=== 同步后的数据库状态 ===')

        # 检查本地用户
        from flowslide.database.database import SessionLocal
        with SessionLocal() as local_session:
            local_users = local_session.execute(
                text("SELECT username FROM users")
            ).fetchall()
            print(f'本地用户: {[u.username for u in local_users]}')

        # 检查外部用户
        if db_mgr.external_engine:
            try:
                with db_mgr.external_engine.connect() as conn:
                    external_users = conn.execute(text('SELECT username FROM users')).fetchall()
                    print(f'外部用户: {[u.username for u in external_users]}')
            except Exception as e:
                print(f'外部数据库查询失败: {e}')

    except Exception as e:
        print(f'手动同步失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    from sqlalchemy import text
    asyncio.run(manual_sync())
