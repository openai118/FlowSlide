#!/usr/bin/env python3
"""
恢复admin用户
"""

import sys
sys.path.append('src')

def restore_admin_user():
    try:
        from flowslide.database.database import SessionLocal, initialize_database
        from flowslide.database.models import User
        from flowslide.services.data_sync_service import DataSyncService
        from sqlalchemy import text
        import asyncio

        # 初始化数据库管理器
        db_mgr = initialize_database()

        print('=== 恢复admin用户 ===')

        # 1. 检查是否已存在admin用户
        with SessionLocal() as local_session:
            existing_admin = local_session.query(User).filter(User.username == 'admin').first()
            if existing_admin:
                print('✅ admin用户已存在，无需恢复')
                return

        # 2. 创建admin用户
        print('\n--- 创建admin用户 ---')
        with SessionLocal() as local_session:
            admin_user = User(
                username='admin',
                email='admin@flowslide.com',
                is_admin=True
            )
            admin_user.set_password('admin123')  # 设置默认密码
            local_session.add(admin_user)
            local_session.commit()
            print('✅ admin用户已创建')
            print(f'  用户名: admin')
            print(f'  邮箱: admin@flowslide.com')
            print(f'  管理员: 是')
            print(f'  默认密码: admin123')

        # 3. 执行同步
        print('\n--- 执行同步 ---')
        sync_service = DataSyncService()
        asyncio.run(sync_service.sync_data())
        print('✅ 同步完成')

        # 4. 验证恢复结果
        print('\n--- 验证恢复结果 ---')
        with SessionLocal() as local_session:
            admin_user = local_session.query(User).filter(User.username == 'admin').first()
            if admin_user:
                print('✅ 本地数据库: admin用户存在')
            else:
                print('❌ 本地数据库: admin用户不存在')

        if db_mgr.external_engine:
            with db_mgr.external_engine.connect() as conn:
                external_admin = conn.execute(
                    text("SELECT username, email FROM users WHERE username = 'admin'")
                ).fetchone()
                if external_admin:
                    print('✅ 外部数据库: admin用户已同步')
                else:
                    print('❌ 外部数据库: admin用户未同步')

        print('\n=== admin用户恢复完成 ===')
        print('\n📝 重要提醒:')
        print('- 请及时修改默认密码 admin123')
        print('- 建议使用强密码保护管理员账户')
        print('- 定期备份重要用户数据')

    except Exception as e:
        print(f'恢复失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    restore_admin_user()
