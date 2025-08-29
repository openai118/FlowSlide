#!/usr/bin/env python3
"""
检查当前用户状态并执行同步
"""

import asyncio
import sys
sys.path.append('src')

async def check_and_sync():
    try:
        from flowslide.database.database import SessionLocal, initialize_database
        from flowslide.services.data_sync_service import DataSyncService
        from sqlalchemy import text

        # 初始化数据库管理器
        db_mgr = initialize_database()

        print('=== 当前用户状态检查 ===')

        # 1. 检查本地数据库用户
        print('\n--- 本地数据库用户 ---')
        with SessionLocal() as local_session:
            local_users = local_session.execute(text("SELECT id, username, email, is_admin, created_at FROM users")).fetchall()
            print(f'本地用户数量: {len(local_users)}')
            for user in local_users:
                print(f'  ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}, 管理员: {user.is_admin}')

        # 2. 检查外部数据库用户
        print('\n--- 外部数据库用户 ---')
        if db_mgr.external_engine:
            with db_mgr.external_engine.connect() as conn:
                external_users = conn.execute(text('SELECT id, username, email, is_admin, created_at FROM users')).fetchall()
                print(f'外部用户数量: {len(external_users)}')
                for user in external_users:
                    print(f'  ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}, 管理员: {user.is_admin}')
        else:
            print('❌ 外部数据库未连接')

        # 3. 执行同步
        print('\n--- 执行同步 ---')
        sync_service = DataSyncService()
        print(f'同步方向: {sync_service.sync_directions}')
        print(f'同步模式: {sync_service.sync_mode}')
        print(f'最后同步时间: {sync_service.last_sync_time}')

        await sync_service.sync_data()
        print('✅ 同步完成')

        # 4. 同步后的状态检查
        print('\n--- 同步后的状态 ---')
        with SessionLocal() as local_session:
            local_users = local_session.execute(text("SELECT id, username, email, is_admin FROM users")).fetchall()
            print(f'本地用户数量: {len(local_users)}')
            for user in local_users:
                print(f'  ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}, 管理员: {user.is_admin}')

        if db_mgr.external_engine:
            with db_mgr.external_engine.connect() as conn:
                external_users = conn.execute(text('SELECT id, username, email, is_admin FROM users')).fetchall()
                print(f'外部用户数量: {len(external_users)}')
                for user in external_users:
                    print(f'  ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}, 管理员: {user.is_admin}')

        # 5. 比较结果
        print('\n--- 同步结果比较 ---')
        with SessionLocal() as local_session:
            local_count = local_session.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]

        if db_mgr.external_engine:
            with db_mgr.external_engine.connect() as conn:
                external_count = conn.execute(text('SELECT COUNT(*) FROM users')).fetchone()[0]

            if local_count == external_count:
                print(f'✅ 用户数量一致: 本地 {local_count} 个, 外部 {external_count} 个')
            else:
                print(f'❌ 用户数量不一致: 本地 {local_count} 个, 外部 {external_count} 个')

        print('\n=== 状态检查完成 ===')

    except Exception as e:
        print(f'状态检查失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_and_sync())
