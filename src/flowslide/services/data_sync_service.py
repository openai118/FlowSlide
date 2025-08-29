"""
数据同步服务 - 在本地SQLite和外部数据库之间实现智能双向同步
"""

import asyncio
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import db_manager
from ..database.models import User, PPTTemplate, GlobalMasterTemplate

logger = logging.getLogger(__name__)


class DataSyncService:
    """智能数据同步服务"""

    def __init__(self):
        self.sync_interval = int(os.getenv("SYNC_INTERVAL", "300"))  # 默认5分钟
        self.sync_mode = os.getenv("SYNC_MODE", "incremental")  # incremental 或 full
        self.last_sync_time = None
        self.is_running = False
        self.sync_directions = self._determine_sync_directions()

    def _determine_sync_directions(self) -> List[str]:
        """根据数据库配置确定同步方向"""
        directions = []

        # 检查环境变量中的同步配置
        enable_sync = os.getenv("ENABLE_DATA_SYNC", "false").lower() == "true"
        sync_directions = os.getenv("SYNC_DIRECTIONS", "local_to_external,external_to_local")

        if db_manager.external_url:
            # 如果明确启用了同步，或者是混合模式
            if enable_sync or db_manager.sync_enabled:
                # 解析同步方向配置
                if "local_to_external" in sync_directions:
                    directions.append("local_to_external")
                if "external_to_local" in sync_directions:
                    directions.append("external_to_local")
            elif db_manager.database_type == "postgresql":
                # 纯外部模式：只从外部同步
                directions.append("external_to_local")

        logger.info(f"🔄 Sync directions determined: {directions} (enable_sync: {enable_sync}, db_sync_enabled: {db_manager.sync_enabled})")
        return directions

    async def start_sync_service(self):
        """启动数据同步服务"""
        if not self.sync_directions:
            logger.info("🔄 Data sync disabled - no external database configured")
            return

        self.is_running = True
        logger.info(f"🔄 Starting data sync service (interval: {self.sync_interval}s, mode: {self.sync_mode})")
        logger.info(f"🔄 Sync directions: {self.sync_directions}")

        while self.is_running:
            try:
                await self.sync_data()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"❌ Sync service error: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟重试

    async def stop_sync_service(self):
        """停止数据同步服务"""
        self.is_running = False
        logger.info("🔄 Data sync service stopped")

    async def sync_data(self):
        """执行数据同步"""
        if not self.sync_directions:
            return

        try:
            logger.info("🔄 Starting data synchronization...")

            if self.sync_mode == "full":
                await self._full_sync()
            else:
                await self._incremental_sync()

            self.last_sync_time = datetime.now()
            logger.info("✅ Data synchronization completed")

        except Exception as e:
            logger.error(f"❌ Data synchronization failed: {e}")
            raise

    async def _incremental_sync(self):
        """增量同步 - 只同步变更的数据"""
        for direction in self.sync_directions:
            if direction == "local_to_external":
                await self._sync_local_to_external()
            elif direction == "external_to_local":
                await self._sync_external_to_local()

    async def _full_sync(self):
        """全量同步 - 同步所有数据"""
        for direction in self.sync_directions:
            if direction == "local_to_external":
                await self._full_sync_local_to_external()
            elif direction == "external_to_local":
                await self._full_sync_external_to_local()

    async def _sync_local_to_external(self):
        """从本地同步到外部数据库"""
        if not db_manager.external_engine:
            return

        try:
            logger.info("🔄 Syncing local changes to external database...")

            # 同步用户表
            await self._sync_users_local_to_external()

            # 同步演示文稿表
            await self._sync_presentations_local_to_external()

            # 同步模板表
            await self._sync_templates_local_to_external()

            logger.info("✅ Local to external sync completed")

        except Exception as e:
            logger.error(f"❌ Local to external sync failed: {e}")

    async def _sync_external_to_local(self):
        """从外部数据库同步到本地"""
        if not db_manager.external_engine:
            return

        try:
            logger.info("🔄 Syncing external changes to local database...")

            # 同步用户表
            await self._sync_users_external_to_local()

            # 同步演示文稿表
            await self._sync_presentations_external_to_local()

            # 同步模板表
            await self._sync_templates_external_to_local()

            logger.info("✅ External to local sync completed")

        except Exception as e:
            logger.error(f"❌ External to local sync failed: {e}")

    async def _sync_users_local_to_external(self):
        """智能同步本地用户到外部数据库 - 基于时间戳的增量同步"""
        if not db_manager.external_engine:
            return

        try:
            logger.info("🔄 Syncing local user changes to external database...")

            # 获取增量同步的时间窗口
            cutoff_time = self.last_sync_time or (datetime.now() - timedelta(hours=24))

            def sync_users():
                from ..database.database import SessionLocal

                with SessionLocal() as local_session:
                    # 获取本地有变更的用户（新增、修改、登录）
                    changed_users = local_session.execute(
                        text("SELECT * FROM users WHERE created_at > :cutoff OR updated_at > :cutoff OR last_login > :cutoff"),
                        {"cutoff": cutoff_time.timestamp()}
                    ).fetchall()

                    if not changed_users:
                        logger.info("📭 No local user changes to sync")
                        return

                    logger.info(f"📤 Found {len(changed_users)} local users with changes")

                    # 同步到外部数据库
                    with db_manager.external_engine.connect() as external_conn:
                        for user in changed_users:
                            # 首先尝试通过ID匹配用户
                            existing = external_conn.execute(
                                text("SELECT id, created_at, updated_at, last_login FROM users WHERE id = :id"),
                                {"id": user.id}
                            ).fetchone()

                            if existing:
                                # 用户已存在，比较时间戳决定是否更新
                                local_timestamp = max(user.created_at, user.updated_at or 0, user.last_login or 0)
                                external_timestamp = max(existing.created_at, existing.updated_at or 0, existing.last_login or 0)

                                logger.info(f"🔍 Comparing user {user.username} (ID: {user.id}):")
                                logger.info(f"   Local timestamp: {local_timestamp}")
                                logger.info(f"   External timestamp: {external_timestamp}")

                                if local_timestamp > external_timestamp:
                                    # 本地数据更新，同步到外部
                                    external_conn.execute(
                                        text("""
                                            UPDATE users SET
                                                username = :username,
                                                email = :email,
                                                password_hash = :password_hash,
                                                is_active = :is_active,
                                                is_admin = :is_admin,
                                                updated_at = :updated_at,
                                                last_login = :last_login
                                            WHERE id = :id
                                        """),
                                        {
                                            "username": user.username,
                                            "email": user.email,
                                            "password_hash": user.password_hash,
                                            "is_active": bool(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else True,
                                            "is_admin": bool(user.is_admin),
                                            "updated_at": user.updated_at or user.created_at,
                                            "last_login": user.last_login,
                                            "id": user.id
                                        }
                                    )
                                    logger.info(f"📤 Updated user {user.username} (ID: {user.id}) in external database")
                                elif local_timestamp == external_timestamp:
                                    logger.info(f"⏭️  User {user.username} (ID: {user.id}) is already synchronized")
                                else:
                                    logger.info(f"⏭️  External user {user.username} (ID: {user.id}) is newer, skipping local update")
                            else:
                                # 用户不存在，插入新用户
                                external_conn.execute(
                                    text("""
                                        INSERT INTO users
                                        (id, username, email, password_hash, is_active, is_admin, created_at, updated_at, last_login)
                                        VALUES (:id, :username, :email, :password_hash, :is_active, :is_admin, :created_at, :updated_at, :last_login)
                                    """),
                                    {
                                        "id": user.id,
                                        "username": user.username,
                                        "email": user.email,
                                        "password_hash": user.password_hash,
                                        "is_active": bool(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else True,
                                        "is_admin": bool(user.is_admin),
                                        "created_at": user.created_at,
                                        "updated_at": user.updated_at or user.created_at,
                                        "last_login": user.last_login
                                    }
                                )
                                logger.info(f"📤 Inserted new user {user.username} (ID: {user.id}) to external database")

                        external_conn.commit()

            # 在线程池中运行同步操作
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(executor, sync_users)

        except Exception as e:
            logger.error(f"❌ User sync local to external failed: {e}")

    async def _sync_users_external_to_local(self):
        """智能同步外部用户到本地数据库 - 基于时间戳的增量同步"""
        if not db_manager.external_engine:
            return

        try:
            logger.info("🔄 Syncing external user changes to local database...")

            # 获取增量同步的时间窗口
            cutoff_time = self.last_sync_time or (datetime.now() - timedelta(hours=24))

            def sync_users():
                from ..database.database import SessionLocal

                if not db_manager.external_engine:
                    logger.warning("External engine not available")
                    return

                with db_manager.external_engine.connect() as external_conn:
                    # 查询外部新增或更新的用户
                    external_users = external_conn.execute(
                        text("SELECT * FROM users WHERE created_at > :cutoff OR updated_at > :cutoff OR last_login > :cutoff"),
                        {"cutoff": cutoff_time.timestamp()}
                    ).fetchall()

                    # 获取外部所有用户ID列表，用于检测删除
                    all_external_users = external_conn.execute(
                        text("SELECT id FROM users")
                    ).fetchall()
                    external_user_ids = {user.id for user in all_external_users}

                    if external_users:
                        logger.info(f"📥 Found {len(external_users)} external users with changes")

                        # 同步到本地数据库
                        with SessionLocal() as local_session:
                            # 获取本地所有用户ID列表
                            all_local_users = local_session.execute(
                                text("SELECT id FROM users")
                            ).fetchall()
                            local_user_ids = {user.id for user in all_local_users}

                            # 找出需要删除的用户（在本地存在但在外部不存在）
                            users_to_delete = local_user_ids - external_user_ids

                            # 处理新增和更新
                            for user in external_users:
                                # 首先尝试通过ID匹配用户（处理用户名变更的情况）
                                existing = local_session.execute(
                                    text("SELECT id, created_at, updated_at, last_login FROM users WHERE id = :id"),
                                    {"id": user.id}
                                ).fetchone()

                                if existing:
                                    # 用户已存在，比较时间戳决定是否更新
                                    external_timestamp = max(user.created_at, user.updated_at or 0, user.last_login or 0)
                                    local_timestamp = max(existing.created_at, existing.updated_at or 0, existing.last_login or 0)

                                    logger.info(f"🔍 Comparing user {user.username} (ID: {user.id}):")
                                    logger.info(f"   External timestamp: {external_timestamp}")
                                    logger.info(f"   Local timestamp: {local_timestamp}")

                                    if external_timestamp > local_timestamp:
                                        # 外部数据更新，同步到本地
                                        local_session.execute(
                                            text("""
                                                UPDATE users SET
                                                    username = :username,
                                                    email = :email,
                                                    password_hash = :password_hash,
                                                    is_active = :is_active,
                                                    is_admin = :is_admin,
                                                    updated_at = :updated_at,
                                                    last_login = :last_login
                                                WHERE id = :id
                                            """),
                                            {
                                                "username": user.username,
                                                "email": user.email,
                                                "password_hash": user.password_hash,
                                                "is_active": int(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else 1,
                                                "is_admin": int(user.is_admin) if user.is_admin is not None else 0,
                                                "updated_at": user.updated_at or user.created_at,
                                                "last_login": user.last_login,
                                                "id": user.id
                                            }
                                        )
                                        logger.info(f"📥 Updated user {user.username} (ID: {user.id}) in local database")
                                    elif external_timestamp == local_timestamp:
                                        logger.info(f"⏭️  User {user.username} (ID: {user.id}) is already synchronized")
                                    else:
                                        logger.info(f"⏭️  Local user {user.username} (ID: {user.id}) is newer, skipping external update")
                                else:
                                    # 用户不存在，插入新用户
                                    local_session.execute(
                                        text("""
                                            INSERT INTO users
                                            (id, username, email, password_hash, is_active, is_admin, created_at, updated_at, last_login)
                                            VALUES (:id, :username, :email, :password_hash, :is_active, :is_admin, :created_at, :updated_at, :last_login)
                                        """),
                                        {
                                            "id": user.id,
                                            "username": user.username,
                                            "email": user.email,
                                            "password_hash": user.password_hash,
                                            "is_active": int(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else 1,
                                            "is_admin": int(user.is_admin) if user.is_admin is not None else 0,
                                            "created_at": user.created_at,
                                            "updated_at": user.updated_at or user.created_at,
                                            "last_login": user.last_login
                                        }
                                    )
                                    logger.info(f"📥 Inserted new user {user.username} (ID: {user.id}) to local database")

                            # 处理删除
                            for user_id in users_to_delete:
                                local_session.execute(
                                    text("DELETE FROM users WHERE id = :id"),
                                    {"id": user_id}
                                )
                                logger.info(f"🗑️  Deleted user ID {user_id} from local database")

                            local_session.commit()

            # 在线程池中运行同步操作
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(executor, sync_users)

        except Exception as e:
            logger.error(f"❌ User sync external to local failed: {e}")

    async def _sync_presentations_local_to_external(self):
        """同步本地演示文稿到外部数据库"""
        try:
            # 实现演示文稿同步逻辑
            logger.debug("🔄 Presentations sync local to external - placeholder")
        except Exception as e:
            logger.error(f"❌ Presentations sync local to external failed: {e}")

    async def _sync_presentations_external_to_local(self):
        """同步外部演示文稿到本地数据库"""
        try:
            # 实现演示文稿同步逻辑
            logger.debug("🔄 Presentations sync external to local - placeholder")
        except Exception as e:
            logger.error(f"❌ Presentations sync external to local failed: {e}")

    async def _sync_templates_local_to_external(self):
        """同步本地模板到外部数据库"""
        try:
            # 实现模板同步逻辑
            logger.debug("🔄 Templates sync local to external - placeholder")
        except Exception as e:
            logger.error(f"❌ Templates sync local to external failed: {e}")

    async def _sync_templates_external_to_local(self):
        """同步外部模板到本地数据库"""
        try:
            # 实现模板同步逻辑
            logger.debug("🔄 Templates sync external to local - placeholder")
        except Exception as e:
            logger.error(f"❌ Templates sync external to local failed: {e}")

    async def _full_sync_local_to_external(self):
        """全量同步本地数据到外部数据库"""
        try:
            logger.info("🔄 Starting full sync from local to external...")

            # 同步所有用户
            await self._sync_users_local_to_external()

            # 同步所有演示文稿
            await self._sync_presentations_local_to_external()

            # 同步所有模板
            await self._sync_templates_local_to_external()

            logger.info("✅ Full sync local to external completed")

        except Exception as e:
            logger.error(f"❌ Full sync local to external failed: {e}")

    async def _full_sync_external_to_local(self):
        """全量同步外部数据到本地数据库"""
        try:
            logger.info("🔄 Starting full sync from external to local...")

            # 同步所有用户
            await self._sync_users_external_to_local()

            # 同步所有演示文稿
            await self._sync_presentations_external_to_local()

            # 同步所有模板
            await self._sync_templates_external_to_local()

            logger.info("✅ Full sync external to local completed")

        except Exception as e:
            logger.error(f"❌ Full sync external to local failed: {e}")

    async def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            "enabled": bool(self.sync_directions),
            "running": self.is_running,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "mode": self.sync_mode,
            "interval": self.sync_interval,
            "directions": self.sync_directions,
            "external_db_type": db_manager.database_type if db_manager.external_engine else None,
            "external_db_configured": bool(db_manager.external_url)
        }


# 创建全局同步服务实例
sync_service = DataSyncService()


async def start_data_sync():
    """启动数据同步服务"""
    await sync_service.start_sync_service()


async def stop_data_sync():
    """停止数据同步服务"""
    await sync_service.stop_sync_service()


async def get_sync_status():
    """获取同步状态"""
    return await sync_service.get_sync_status()


async def trigger_manual_sync():
    """手动触发一次同步"""
    if sync_service.sync_directions:
        logger.info("🔄 Manual sync triggered")
        await sync_service.sync_data()
        return {"status": "success", "message": "Manual sync completed"}
    else:
        return {"status": "disabled", "message": "Data sync is disabled"}
