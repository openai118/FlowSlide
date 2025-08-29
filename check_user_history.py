#!/usr/bin/env python3
"""
检查用户历史和可能的删除原因
"""

import sys
sys.path.append('src')

def check_user_history():
    try:
        from flowslide.database.database import SessionLocal, initialize_database
        from sqlalchemy import text

        # 初始化数据库管理器
        db_mgr = initialize_database()

        print('=== 用户历史检查 ===')

        # 1. 检查本地数据库中的所有用户
        print('\n--- 本地数据库完整检查 ---')
        with SessionLocal() as local_session:
            # 查询所有用户
            all_users = local_session.execute(text("SELECT * FROM users")).fetchall()
            print(f'本地数据库用户总数: {len(all_users)}')

            for user in all_users:
                print(f'  ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}')
                print(f'    创建时间: {user.created_at}, 最后登录: {user.last_login}')
                print(f'    管理员: {user.is_admin}, 激活状态: {user.is_active}')

        # 2. 检查外部数据库中的所有用户
        print('\n--- 外部数据库完整检查 ---')
        if db_mgr.external_engine:
            with db_mgr.external_engine.connect() as conn:
                all_external_users = conn.execute(text('SELECT * FROM users')).fetchall()
                print(f'外部数据库用户总数: {len(all_external_users)}')

                for user in all_external_users:
                    print(f'  ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}')
                    print(f'    创建时间: {user.created_at}, 最后登录: {user.last_login}')
                    print(f'    管理员: {user.is_admin}, 激活状态: {user.is_active}')

        # 3. 检查是否存在admin或try1用户
        print('\n--- 查找admin和try1用户 ---')
        with SessionLocal() as local_session:
            admin_user = local_session.execute(
                text("SELECT * FROM users WHERE username = 'admin' OR username = 'try1'")
            ).fetchall()

            if admin_user:
                print('✅ 找到admin或try1用户:')
                for user in admin_user:
                    print(f'  ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}')
            else:
                print('❌ 本地数据库中没有找到admin或try1用户')

        if db_mgr.external_engine:
            with db_mgr.external_engine.connect() as conn:
                external_admin = conn.execute(
                    text("SELECT * FROM users WHERE username = 'admin' OR username = 'try1'")
                ).fetchall()

                if external_admin:
                    print('✅ 外部数据库中找到admin或try1用户:')
                    for user in external_admin:
                        print(f'  ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}')
                else:
                    print('❌ 外部数据库中没有找到admin或try1用户')

        # 4. 检查可能的删除原因
        print('\n--- 分析可能的删除原因 ---')

        # 检查同步服务配置
        from flowslide.services.data_sync_service import DataSyncService
        sync_service = DataSyncService()

        print(f'同步方向: {sync_service.sync_directions}')
        print(f'同步模式: {sync_service.sync_mode}')
        print(f'最后同步时间: {sync_service.last_sync_time}')
        print(f'同步间隔: {sync_service.sync_interval}秒')

        # 检查数据库配置
        print(f'数据库类型: {db_mgr.database_type}')
        print(f'同步启用: {db_mgr.sync_enabled}')
        print(f'外部数据库URL: {db_mgr.external_url}')

        print('\n=== 可能的原因分析 ===')
        print('1. 手动删除：在之前的测试或操作中被手动删除')
        print('2. 同步删除：在旧的同步逻辑中被错误删除')
        print('3. 数据清理：在数据库清理操作中被删除')
        print('4. 应用重启：某些用户可能没有持久化保存')

        print('\n建议：')
        print('- 如果需要恢复admin用户，可以重新创建')
        print('- 检查应用日志，看是否有删除操作的记录')
        print('- 确认是否在测试过程中执行了清理操作')

    except Exception as e:
        print(f'检查失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_user_history()
