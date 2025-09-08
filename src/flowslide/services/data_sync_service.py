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
from sqlalchemy.exc import IntegrityError
import tempfile
import zipfile
import sqlite3
import shutil
from pathlib import Path

from ..database import db_manager
from ..database.models import User, PPTTemplate, GlobalMasterTemplate, SyncConflict
from ..services.backup_service import backup_service, list_r2_files
from ..core.deployment_mode_manager import mode_manager
from ..core.sync_strategy_config import DeploymentMode, sync_strategy_config

logger = logging.getLogger(__name__)


class DataSyncService:
    """智能数据同步服务"""

    def __init__(self):
        self.sync_interval = int(os.getenv("SYNC_INTERVAL", "300"))  # 默认5分钟
        self.sync_mode = os.getenv("SYNC_MODE", "incremental")  # incremental 或 full
        self.last_sync_time = None
        self.is_running = False
        self.sync_directions = self._determine_sync_directions()
        # 决定用户名/用户数据的权威来源: 'external' 或 'local'
        # 默认：如果配置了外部数据库则外部为权威，否则本地为权威
        self.authoritative_source = os.getenv(
            "SYNC_AUTHORITATIVE",
            "external" if db_manager.external_engine else "local",
        ).lower()

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
        # Re-evaluate directions and authoritative source at startup because
        # db_manager may have been initialized after this service instance was created.
        try:
            self.sync_directions = self._determine_sync_directions()
        except Exception:
            # keep previous value if determination fails
            pass

        try:
            self.authoritative_source = os.getenv(
                "SYNC_AUTHORITATIVE",
                "external" if db_manager.external_engine else "local",
            ).lower()
        except Exception:
            pass

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
        """从本地同步到外部数据库（仅限 local_external / local_external_r2 模式）"""
        from ..core.mode_manager import mode_manager, DeploymentMode
        try:
            current_mode = mode_manager.current_mode or mode_manager.detect_current_mode()
        except Exception:
            current_mode = None
        if current_mode not in (DeploymentMode.LOCAL_EXTERNAL, DeploymentMode.LOCAL_EXTERNAL_R2):
            logger.info(f"⏭️ 当前模式 {current_mode} 不允许与 external 同步，跳过 _sync_local_to_external")
            return
        if not db_manager.external_engine:
            return
        try:
            logger.info("🔄 Syncing local changes to external database...")
            # Note: User sync disabled as per requirements
            # await self._sync_users_local_to_external()
            # 同步演示文稿表
            await self._sync_presentations_local_to_external()
            # 同步模板表
            await self._sync_templates_local_to_external()
            # 同步配置文件
            await self._sync_configs_local_to_external()
            logger.info("✅ Local to external sync completed")
        except Exception as e:
            logger.error(f"❌ Local to external sync failed: {e}")

    async def _sync_external_to_local(self):
        """从外部数据库同步到本地（仅限 local_external / local_external_r2 模式）"""
        from ..core.mode_manager import mode_manager, DeploymentMode
        try:
            current_mode = mode_manager.current_mode or mode_manager.detect_current_mode()
        except Exception:
            current_mode = None
        if current_mode not in (DeploymentMode.LOCAL_EXTERNAL, DeploymentMode.LOCAL_EXTERNAL_R2):
            logger.info(f"⏭️ 当前模式 {current_mode} 不允许与 external 同步，跳过 _sync_external_to_local")
            return
        if not db_manager.external_engine:
            return
        try:
            logger.info("🔄 Syncing external changes to local database...")
            # Note: User sync disabled as per requirements
            # await self._sync_users_external_to_local()
            # 同步演示文稿表
            await self._sync_presentations_external_to_local()
            # 同步模板表
            await self._sync_templates_external_to_local()
            # 同步配置文件
            await self._sync_configs_external_to_local()
            logger.info("✅ External to local sync completed")
        except Exception as e:
            logger.error(f"❌ External to local sync failed: {e}")

    async def _sync_users_local_to_external(self):
        """智能同步本地用户到外部数据库 - 基于时间戳的增量同步"""
        if not db_manager.external_engine:
            return

        # If external is authoritative, normally avoid overwriting external data.
        # However, for three-way mode (LOCAL_EXTERNAL_R2) we must still propagate local creates/deletes
        # and perform controlled updates. Determine current mode to decide.
        try:
            try:
                current_mode = mode_manager.current_mode or mode_manager.detect_current_mode()
            except Exception:
                current_mode = mode_manager.detect_current_mode()
        except Exception:
            current_mode = None

        if self.authoritative_source == "external" and current_mode not in (DeploymentMode.LOCAL_EXTERNAL_R2, DeploymentMode.LOCAL_EXTERNAL):
            logger.info("🔒 External DB is authoritative for user data - skipping local->external user sync to avoid overwriting external usernames")
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
                    with db_manager.external_engine.connect() as external_conn:  # type: ignore[union-attr]
                        for user in changed_users:
                            # Safer approach: prefer to find external user by username first, then by id.
                            existing_by_id = external_conn.execute(
                                text("SELECT id, created_at, updated_at, last_login, username FROM users WHERE id = :id"),
                                {"id": user.id}
                            ).fetchone()

                            existing_by_username = external_conn.execute(
                                text("SELECT id, created_at, updated_at, last_login, username FROM users WHERE username = :username"),
                                {"username": user.username}
                            ).fetchone()

                            try:
                                if existing_by_id:
                                    # If username is taken by a different external id, record conflict
                                    if existing_by_username and existing_by_username.id != existing_by_id.id:
                                        from ..database.database import SessionLocal as _SessionLocal
                                        with _SessionLocal() as session:
                                            sc = SyncConflict(
                                                local_id=user.id,
                                                external_id=existing_by_username.id,
                                                attempted_username=user.username,
                                                reason="username_conflict_on_update",
                                                payload={"local": {"id": user.id, "username": user.username}, "external": {"id": existing_by_username.id}},
                                            )
                                            session.add(sc)
                                            session.commit()
                                        logger.warning(f"⚠️ Username conflict when updating user {user.username} (local id {user.id}) - recorded to sync_conflicts and skipped")
                                    else:
                                        # Compare timestamps and update if local is newer
                                        local_timestamp = max(user.created_at, user.updated_at or 0, user.last_login or 0)
                                        external_timestamp = max(existing_by_id.created_at, existing_by_id.updated_at or 0, existing_by_id.last_login or 0)

                                        if local_timestamp > external_timestamp:
                                            # Update external row by id with latest local fields
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
                                                    "id": existing_by_id.id,
                                                }
                                            )
                                            logger.info(f"📤 Updated user {user.username} (external id {existing_by_id.id}) in external database")
                                        else:
                                            logger.info(f"⏭️  User {user.username} (local id {user.id}) is not newer than external; skipping")

                                else:
                                    # No external row with same id. If there's a row with same username, update it.
                                    if existing_by_username:
                                        external_timestamp = max(existing_by_username.created_at, existing_by_username.updated_at or 0, existing_by_username.last_login or 0)
                                        local_timestamp = max(user.created_at, user.updated_at or 0, user.last_login or 0)
                                        if local_timestamp > external_timestamp:
                                            external_conn.execute(
                                                text("""
                                                    UPDATE users SET
                                                        email = :email,
                                                        password_hash = :password_hash,
                                                        is_active = :is_active,
                                                        is_admin = :is_admin,
                                                        updated_at = :updated_at,
                                                        last_login = :last_login
                                                    WHERE id = :id
                                                """),
                                                {
                                                    "email": user.email,
                                                    "password_hash": user.password_hash,
                                                    "is_active": bool(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else True,
                                                    "is_admin": bool(user.is_admin),
                                                    "updated_at": user.updated_at or user.created_at,
                                                    "last_login": user.last_login,
                                                    "id": existing_by_username.id,
                                                }
                                            )
                                            logger.info(f"📤 Updated user {user.username} (external id {existing_by_username.id}) in external database")
                                        else:
                                            logger.info(f"⏭️  External user {user.username} is newer; skipping")
                                    else:
                                        # Safe insert: do not force id; insert by username so external assigns id
                                        try:
                                            external_conn.execute(
                                                text("""
                                                    INSERT INTO users
                                                    (username, email, password_hash, is_active, is_admin, created_at, updated_at, last_login)
                                                    VALUES (:username, :email, :password_hash, :is_active, :is_admin, :created_at, :updated_at, :last_login)
                                                """),
                                                {
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
                                            logger.info(f"📤 Inserted new user {user.username} to external database (id assigned by external DB)")
                                        except IntegrityError as ie_insert:
                                            # Try to recover: if duplicate username, convert to update
                                            msg = str(ie_insert).lower()
                                            if "duplicate" in msg or "unique" in msg:
                                                try:
                                                    external_conn.execute(
                                                        text("""
                                                            UPDATE users SET
                                                                email = :email,
                                                                password_hash = :password_hash,
                                                                is_active = :is_active,
                                                                is_admin = :is_admin,
                                                                updated_at = :updated_at,
                                                                last_login = :last_login
                                                            WHERE username = :username
                                                        """),
                                                        {
                                                            "email": user.email,
                                                            "password_hash": user.password_hash,
                                                            "is_active": bool(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else True,
                                                            "is_admin": bool(user.is_admin),
                                                            "updated_at": user.updated_at or user.created_at,
                                                            "last_login": user.last_login,
                                                            "username": user.username,
                                                        }
                                                    )
                                                    logger.info(f"🔁 Recovered from duplicate insert by updating external user {user.username}")
                                                except Exception:
                                                    try:
                                                        external_conn.rollback()
                                                    except Exception:
                                                        pass
                                                    from ..database.database import SessionLocal as _SessionLocal
                                                    with _SessionLocal() as session:
                                                        sc = SyncConflict(
                                                            local_id=user.id,
                                                            external_id=None,
                                                            attempted_username=user.username,
                                                            reason="integrity_error_on_external",
                                                            payload={"error": str(ie_insert), "local": {"id": user.id, "username": user.username}},
                                                        )
                                                        session.add(sc)
                                                        session.commit()
                                                    logger.warning(f"⚠️ IntegrityError when syncing user {user.username} to external DB: {ie_insert} - recorded to sync_conflicts and skipped")
                                            else:
                                                try:
                                                    external_conn.rollback()
                                                except Exception:
                                                    pass
                                                from ..database.database import SessionLocal as _SessionLocal
                                                with _SessionLocal() as session:
                                                    sc = SyncConflict(
                                                        local_id=user.id,
                                                        external_id=None,
                                                        attempted_username=user.username,
                                                        reason="integrity_error_on_external",
                                                        payload={"error": str(ie_insert), "local": {"id": user.id, "username": user.username}},
                                                    )
                                                    session.add(sc)
                                                    session.commit()
                                                logger.warning(f"⚠️ IntegrityError when syncing user {user.username} to external DB: {ie_insert} - recorded to sync_conflicts and skipped")
                            except IntegrityError as ie:
                                try:
                                    external_conn.rollback()
                                except Exception:
                                    pass
                                from ..database.database import SessionLocal as _SessionLocal

                                with _SessionLocal() as session:
                                    sc = SyncConflict(
                                        local_id=user.id,
                                        external_id=None,
                                        attempted_username=user.username,
                                        reason="integrity_error_on_external",
                                        payload={"error": str(ie), "local": {"id": user.id, "username": user.username}},
                                    )
                                    session.add(sc)
                                    session.commit()

                                logger.warning(f"⚠️ IntegrityError when syncing user {user.username} to external DB: {ie} - recorded to sync_conflicts and skipped")

                        try:
                            external_conn.commit()
                        except IntegrityError as ie:
                            try:
                                external_conn.rollback()
                            except Exception:
                                pass
                            from ..database.database import SessionLocal as _SessionLocal

                            with _SessionLocal() as session:
                                sc = SyncConflict(
                                    local_id=None,
                                    external_id=None,
                                    attempted_username=None,
                                    reason="integrity_error_on_commit_external",
                                    payload={"error": str(ie)},
                                )
                                session.add(sc)
                                session.commit()

                            logger.warning(f"⚠️ IntegrityError on external commit: {ie} - recorded to sync_conflicts")

                        # Propagate deletions safely: delete external users whose username no longer exists locally
                        try:
                            all_external = external_conn.execute(text("SELECT id, username FROM users")).fetchall()
                            external_usernames = {r.username for r in all_external}
                            local_usernames = {u.username for u in local_session.execute(text("SELECT username FROM users")).fetchall()}

                            usernames_to_delete = external_usernames - local_usernames
                            if usernames_to_delete:
                                logger.info(f"🗑️ Propagating deletion of {len(usernames_to_delete)} users to external DB")
                                for uname in usernames_to_delete:
                                    try:
                                        row = external_conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": uname}).fetchone()
                                        if not row:
                                            continue
                                        ext_id = row.id
                                        # Prefer soft-delete to avoid FK violations: mark as inactive
                                        try:
                                            # Hard delete: remove dependent sessions then the user
                                            try:
                                                external_conn.execute(text("DELETE FROM user_sessions WHERE user_id = :id"), {"id": ext_id})
                                            except Exception:
                                                pass
                                            external_conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": ext_id})
                                            logger.info(f"🗑️ Hard-deleted external user id={ext_id} username={uname}")
                                        except Exception as e:
                                            # record conflict on failure
                                            try:
                                                external_conn.rollback()
                                            except Exception:
                                                pass
                                            from ..database.database import SessionLocal as _SessionLocal
                                            with _SessionLocal() as session:
                                                sc = SyncConflict(
                                                    local_id=None,
                                                    external_id=ext_id,
                                                    attempted_username=uname,
                                                    reason="error_on_hard_delete_external",
                                                    payload={"error": str(e)}
                                                )
                                                session.add(sc)
                                                session.commit()
                                            logger.warning(f"⚠️ Failed to hard-delete external user username={uname}: {e} - recorded to sync_conflicts")
                                    except Exception as e:
                                        try:
                                            external_conn.rollback()
                                        except Exception:
                                            pass
                                        from ..database.database import SessionLocal as _SessionLocal
                                        with _SessionLocal() as session:
                                            sc = SyncConflict(
                                                local_id=None,
                                                external_id=None,
                                                attempted_username=uname,
                                                reason="error_on_delete_external",
                                                payload={"error": str(e)}
                                            )
                                            session.add(sc)
                                            session.commit()
                                        logger.warning(f"⚠️ Failed to delete external user username={uname}: {e} - recorded to sync_conflicts")

                                try:
                                    external_conn.commit()
                                except Exception:
                                    try:
                                        external_conn.rollback()
                                    except Exception:
                                        pass
                        except Exception as e:
                            logger.warning(f"⚠️ Error while propagating deletions to external: {e}")

            # 在线程池中运行同步操作
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(executor, sync_users)

            # Optionally perform a full upsert of all external users into local.
            # This will run when running in full sync mode or when explicitly enabled
            # via the environment variable SYNC_UPSERT_ALL_USERS=true.
            try:
                # Decide whether to perform a full upsert of external users into local.
                # Criteria:
                #  - explicit full sync mode (self.sync_mode == 'full')
                #  - sync strategy requests startup sync for 'users'
                #  - deployment mode includes external database (local_external or local_external_r2)
                try:
                    current_mode = mode_manager.current_mode or mode_manager.detect_current_mode()
                except Exception:
                    try:
                        current_mode = mode_manager.detect_current_mode()
                    except Exception:
                        current_mode = None

                startup_sync = False
                try:
                    startup_sync = sync_strategy_config.should_startup_sync_for_type("users")
                except Exception:
                    startup_sync = False

                do_full_upsert = (
                    self.sync_mode == "full"
                    or startup_sync
                    or (current_mode in (DeploymentMode.LOCAL_EXTERNAL, DeploymentMode.LOCAL_EXTERNAL_R2))
                )

                if do_full_upsert:
                    logger.info("🔁 Performing full upsert of all external users into local (strategy/mode indicated)")

                    def upsert_all_external_users():
                        from ..database.database import SessionLocal

                        if not db_manager.external_engine:
                            logger.warning("External engine not available for full upsert")
                            return

                        with db_manager.external_engine.connect() as ext_conn:
                            rows = ext_conn.execute(
                                text("SELECT id, username, password_hash, email, is_admin, is_active, created_at, updated_at, last_login FROM users")
                            ).fetchall()

                            if not rows:
                                logger.info("No users found in external DB for full upsert")
                                return

                            created = 0
                            updated = 0
                            now = datetime.now().timestamp()

                            with SessionLocal() as local_session:
                                for r in rows:
                                    try:
                                        ext_id = r[0]
                                        username = r[1]
                                        password_hash = r[2]
                                        email = r[3]
                                        is_admin = bool(r[4]) if len(r) > 4 else False
                                        is_active = bool(r[5]) if len(r) > 5 else True
                                        created_at = r[6] if len(r) > 6 else now
                                        updated_at = r[7] if len(r) > 7 else now
                                        last_login = r[8] if len(r) > 8 else None
                                    except Exception:
                                        mapping = dict(r)
                                        ext_id = mapping.get('id')
                                        username = mapping.get('username')
                                        password_hash = mapping.get('password_hash')
                                        email = mapping.get('email')
                                        is_admin = bool(mapping.get('is_admin'))
                                        is_active = bool(mapping.get('is_active', True))
                                        created_at = mapping.get('created_at', now)
                                        updated_at = mapping.get('updated_at', now)
                                        last_login = mapping.get('last_login')

                                    if not username or not password_hash:
                                        logger.debug(f"Skipping external user with missing username/hash: {ext_id}")
                                        continue

                                    existing = local_session.execute(text("SELECT id FROM users WHERE username=:u LIMIT 1"), {"u": username}).fetchone()
                                    if existing:
                                        local_id = existing[0]
                                        try:
                                            local_session.execute(
                                                text(
                                                    "UPDATE users SET password_hash=:hash, email=:email, is_admin=:is_admin, is_active=:is_active, updated_at=:updated_at, last_login=:last_login WHERE id=:id"
                                                ),
                                                {"hash": password_hash, "email": email, "is_admin": is_admin, "is_active": is_active, "updated_at": updated_at or now, "last_login": last_login, "id": local_id},
                                            )
                                            updated += 1
                                        except IntegrityError as ie:
                                            local_session.rollback()
                                            sc = SyncConflict(
                                                local_id=local_id,
                                                external_id=ext_id,
                                                attempted_username=username,
                                                reason="integrity_error_on_full_upsert_update",
                                                payload={"error": str(ie), "external": {"id": ext_id, "username": username}},
                                            )
                                            local_session.add(sc)
                                            local_session.commit()
                                            logger.warning(f"⚠️ IntegrityError updating local user {username} during full upsert: {ie} - recorded to sync_conflicts")
                                    else:
                                        try:
                                            local_session.execute(
                                                text(
                                                    "INSERT INTO users (id, username, password_hash, email, is_admin, is_active, created_at, updated_at, last_login) VALUES (:id,:username,:hash,:email,:is_admin,:is_active,:created_at,:updated_at,:last_login)"
                                                ),
                                                {"id": ext_id, "username": username, "hash": password_hash, "email": email, "is_admin": is_admin, "is_active": is_active, "created_at": created_at or now, "updated_at": updated_at or now, "last_login": last_login},
                                            )
                                            created += 1
                                        except IntegrityError as ie:
                                            local_session.rollback()
                                            sc = SyncConflict(
                                                local_id=None,
                                                external_id=ext_id,
                                                attempted_username=username,
                                                reason="integrity_error_on_full_upsert_insert",
                                                payload={"error": str(ie), "external": {"id": ext_id, "username": username}},
                                            )
                                            local_session.add(sc)
                                            local_session.commit()
                                            logger.warning(f"⚠️ IntegrityError inserting local user {username} during full upsert: {ie} - recorded to sync_conflicts")

                                try:
                                    local_session.commit()
                                except Exception:
                                    try:
                                        local_session.rollback()
                                    except Exception:
                                        pass

                            logger.info(f"🔁 Full upsert completed: created={created} updated={updated} total_external={len(rows)}")

                    import concurrent.futures as _cf
                    with _cf.ThreadPoolExecutor() as _ex:
                        await asyncio.get_event_loop().run_in_executor(_ex, upsert_all_external_users)

            except Exception as e:
                logger.error(f"❌ Full external->local upsert failed: {e}")

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

                with db_manager.external_engine.connect() as external_conn:  # type: ignore[union-attr]
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
                            local_user_ids = {u.id for u in all_local_users}

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
                                    external_timestamp = max(user.created_at, user.updated_at or 0, user.last_login or 0)
                                    local_timestamp = max(existing.created_at, existing.updated_at or 0, existing.last_login or 0)

                                    logger.info(f"🔍 Comparing user {user.username} (ID: {user.id}):")
                                    logger.info(f"   External timestamp: {external_timestamp}")
                                    logger.info(f"   Local timestamp: {local_timestamp}")

                                    if external_timestamp > local_timestamp:
                                        # 外部数据更新，同步到本地
                                        # 预检测 username 冲突：如果本地存在不同 id 使用相同 username，则记录冲突并跳过
                                        conflict_local = local_session.execute(
                                            text("SELECT id FROM users WHERE username = :username"),
                                            {"username": user.username}
                                        ).fetchone()

                                        if conflict_local and conflict_local.id != user.id:
                                            sc = SyncConflict(
                                                local_id=conflict_local.id,
                                                external_id=user.id,
                                                attempted_username=user.username,
                                                reason="username_conflict_on_external_update",
                                                payload={
                                                    "external": {"id": user.id, "username": user.username},
                                                    "local": {"id": conflict_local.id}
                                                }
                                            )
                                            local_session.add(sc)
                                            local_session.commit()
                                            logger.warning(f"⚠️ Username conflict when applying external update for {user.username} (external id {user.id}) - recorded to sync_conflicts and skipped")
                                        else:
                                            try:
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
                                            except IntegrityError as ie:
                                                local_session.rollback()
                                                sc = SyncConflict(
                                                    local_id=None,
                                                    external_id=user.id,
                                                    attempted_username=user.username,
                                                    reason="integrity_error_on_local_update",
                                                    payload={"error": str(ie), "external": {"id": user.id, "username": user.username}},
                                                )
                                                local_session.add(sc)
                                                local_session.commit()
                                                logger.warning(f"⚠️ IntegrityError when applying external update to local DB for user {user.username}: {ie} - recorded to sync_conflicts and skipped")
                                    elif external_timestamp == local_timestamp:
                                        logger.info(f"⏭️  User {user.username} (ID: {user.id}) is already synchronized")
                                    else:
                                        logger.info(f"⏭️  Local user {user.username} (ID: {user.id}) is newer, skipping external update")
                                else:
                                    # 用户不存在，插入新用户 - 先检测本地 username 冲突
                                    conflict_local = local_session.execute(
                                        text("SELECT id FROM users WHERE username = :username"),
                                        {"username": user.username}
                                    ).fetchone()

                                    if conflict_local:
                                        sc = SyncConflict(
                                            local_id=conflict_local.id,
                                            external_id=user.id,
                                            attempted_username=user.username,
                                            reason="username_conflict_on_external_insert",
                                            payload={"external": {"id": user.id, "username": user.username}, "local": {"id": conflict_local.id}}
                                        )
                                        local_session.add(sc)
                                        local_session.commit()
                                        logger.warning(f"⚠️ Username conflict when inserting external user {user.username} (external id {user.id}) - recorded to sync_conflicts and skipped")
                                    else:
                                        try:
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
                                        except IntegrityError as ie:
                                            local_session.rollback()
                                            sc = SyncConflict(
                                                local_id=None,
                                                external_id=user.id,
                                                attempted_username=user.username,
                                                reason="integrity_error_on_local_insert",
                                                payload={"error": str(ie), "external": {"id": user.id, "username": user.username}},
                                            )
                                            local_session.add(sc)
                                            local_session.commit()
                                            logger.warning(f"⚠️ IntegrityError when inserting external user to local DB {user.username}: {ie} - recorded to sync_conflicts and skipped")

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

            # 如果运行模式为 LOCAL_EXTERNAL_R2，则在 external -> local 之后，
            # 再从 R2 拉取用户快照（作为次要来源）合并到本地，最后触发一次强制的 local -> external 同步
            try:
                try:
                    current_mode = mode_manager.current_mode or mode_manager.detect_current_mode()
                except Exception:
                    current_mode = mode_manager.detect_current_mode()

                if current_mode == DeploymentMode.LOCAL_EXTERNAL_R2:
                    logger.info("🔁 Detected LOCAL_EXTERNAL_R2 mode: merging users from R2 as secondary source")

                    r2_users = await self._get_users_from_r2_latest()
                    if r2_users:
                        logger.info(f"📥 Merging {len(r2_users)} users from R2 (secondary source)")

                        def merge_r2_users():
                            from ..database.database import SessionLocal

                            with SessionLocal() as local_session:
                                for user in r2_users:
                                    existing = local_session.execute(
                                        text("SELECT id, created_at, updated_at, last_login FROM users WHERE id = :id"),
                                        {"id": user.get("id")}
                                    ).fetchone()

                                    r2_timestamp = max(user.get("created_at") or 0, user.get("updated_at") or 0, user.get("last_login") or 0)

                                    if existing:
                                        local_timestamp = max(existing.created_at, existing.updated_at or 0, existing.last_login or 0)
                                        if r2_timestamp > local_timestamp:
                                            # 检测本地 username 冲突
                                            conflict_local = local_session.execute(
                                                text("SELECT id FROM users WHERE username = :username"),
                                                {"username": user.get("username")}
                                            ).fetchone()

                                            if conflict_local and conflict_local.id != user.get("id"):
                                                sc = SyncConflict(
                                                    local_id=conflict_local.id,
                                                    external_id=None,
                                                    attempted_username=user.get("username"),
                                                    reason="username_conflict_on_r2_update",
                                                    payload={"r2": {"id": user.get("id"), "username": user.get("username")}, "local": {"id": conflict_local.id}}
                                                )
                                                local_session.add(sc)
                                                local_session.commit()
                                                logger.warning(f"⚠️ Username conflict when applying R2 update for {user.get('username')} - recorded and skipped")
                                            else:
                                                # 应用 R2 数据到本地
                                                try:
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
                                                            "username": user.get("username"),
                                                            "email": user.get("email"),
                                                            "password_hash": user.get("password_hash"),
                                                            "is_active": int(user.get("is_active", 1)),
                                                            "is_admin": int(user.get("is_admin", 0)),
                                                            "updated_at": user.get("updated_at") or user.get("created_at"),
                                                            "last_login": user.get("last_login"),
                                                            "id": user.get("id")
                                                        }
                                                    )
                                                    logger.info(f"📥 Applied R2 update to local user {user.get('username')} (ID: {user.get('id')})")
                                                except IntegrityError as ie:
                                                    local_session.rollback()
                                                    sc = SyncConflict(
                                                        local_id=None,
                                                        external_id=None,
                                                        attempted_username=user.get("username"),
                                                        reason="integrity_error_on_r2_local_update",
                                                        payload={"error": str(ie), "r2": {"id": user.get("id"), "username": user.get("username")}}
                                                    )
                                                    local_session.add(sc)
                                                    local_session.commit()
                                                    logger.warning(f"⚠️ IntegrityError when applying R2 update to local DB for user {user.get('username')}: {ie} - recorded to sync_conflicts and skipped")
                                    else:
                                        # 本地不存在，插入前检测 username 冲突
                                        conflict_local = local_session.execute(
                                            text("SELECT id FROM users WHERE username = :username"),
                                            {"username": user.get("username")}
                                        ).fetchone()

                                        if conflict_local:
                                            sc = SyncConflict(
                                                local_id=conflict_local.id,
                                                external_id=None,
                                                attempted_username=user.get("username"),
                                                reason="username_conflict_on_r2_insert",
                                                payload={"r2": {"id": user.get("id"), "username": user.get("username")}, "local": {"id": conflict_local.id}}
                                            )
                                            local_session.add(sc)
                                            local_session.commit()
                                            logger.warning(f"⚠️ Username conflict when inserting R2 user {user.get('username')} - recorded to sync_conflicts and skipped")
                                        else:
                                            try:
                                                local_session.execute(
                                                    text("""
                                                        INSERT INTO users
                                                        (id, username, email, password_hash, is_active, is_admin, created_at, updated_at, last_login)
                                                        VALUES (:id, :username, :email, :password_hash, :is_active, :is_admin, :created_at, :updated_at, :last_login)
                                                    """),
                                                    {
                                                        "id": user.get("id"),
                                                        "username": user.get("username"),
                                                        "email": user.get("email"),
                                                        "password_hash": user.get("password_hash"),
                                                        "is_active": int(user.get("is_active", 1)),
                                                        "is_admin": int(user.get("is_admin", 0)),
                                                        "created_at": user.get("created_at"),
                                                        "updated_at": user.get("updated_at") or user.get("created_at"),
                                                        "last_login": user.get("last_login")
                                                    }
                                                )
                                                logger.info(f"📥 Inserted R2 user {user.get('username')} (ID: {user.get('id')}) into local DB")
                                            except IntegrityError as ie:
                                                local_session.rollback()
                                                sc = SyncConflict(
                                                    local_id=None,
                                                    external_id=None,
                                                    attempted_username=user.get("username"),
                                                    reason="integrity_error_on_r2_local_insert",
                                                    payload={"error": str(ie), "r2": {"id": user.get("id"), "username": user.get("username")}}
                                                )
                                                local_session.add(sc)
                                                local_session.commit()
                                                logger.warning(f"⚠️ IntegrityError when inserting R2 user to local DB {user.get('username')}: {ie} - recorded to sync_conflicts and skipped")

                                local_session.commit()

                        # 在线程池运行合并，以避免阻塞事件循环
                        with concurrent.futures.ThreadPoolExecutor() as merge_executor:
                            await asyncio.get_event_loop().run_in_executor(merge_executor, merge_r2_users)

                        # 最后触发一次强制的 local -> external 同步，以将 R2 中的补充数据统一推回 external
                        try:
                            await self._sync_users_local_to_external_force()
                        except Exception as e:
                            logger.error(f"❌ Forced local->external sync after R2 merge failed: {e}")

                    else:
                        logger.info("ℹ️ No usable R2 user snapshot found to merge")
            except Exception as e:
                logger.error(f"❌ Merging users from R2 failed: {e}")

        except Exception as e:
            logger.error(f"❌ User sync external to local failed: {e}")

    async def _sync_presentations_local_to_external(self):
        """同步本地演示文稿到外部数据库"""
        if not db_manager.external_engine:
            return

        try:
            logger.info("🔄 Syncing local presentations to external database...")

            # 获取增量同步的时间窗口
            cutoff_time = self.last_sync_time or (datetime.now() - timedelta(hours=24))


            def sync_presentations():
                from ..database.database import SessionLocal
                import json

                with SessionLocal() as local_session:
                    # 获取本地有变更的项目（新增、修改）
                    changed_projects = local_session.execute(
                        text("SELECT * FROM projects WHERE created_at > :cutoff OR updated_at > :cutoff"),
                        {"cutoff": cutoff_time.timestamp()}
                    ).fetchall()

                    # 获取本地所有项目ID
                    local_project_ids = set([row.project_id for row in local_session.execute(text("SELECT project_id FROM projects")).fetchall()])

                    # 获取外部所有项目ID
                    external_project_ids = set()
                    if db_manager.external_engine:
                        with db_manager.external_engine.connect() as external_conn:
                            external_project_ids = set([row.project_id for row in external_conn.execute(text("SELECT project_id FROM projects")).fetchall()])

                            # 1. 同步删除：本地不存在但外部还存在的项目，删除外部
                            to_delete = external_project_ids - local_project_ids
                            if to_delete:
                                for pid in to_delete:
                                    external_conn.execute(text("DELETE FROM projects WHERE project_id = :project_id"), {"project_id": pid})
                                    logger.info(f"🗑️ Deleted project {pid} from external database (local no longer exists)")

                            # 2. 同步新增/修改
                            if not changed_projects:
                                logger.info("📭 No local presentation changes to sync")
                                return

                            logger.info(f"📤 Found {len(changed_projects)} local presentations with changes")

                            for project in changed_projects:
                                # 首先尝试通过project_id匹配项目
                                existing = external_conn.execute(
                                    text("SELECT id, project_id, created_at, updated_at FROM projects WHERE project_id = :project_id"),
                                    {"project_id": project.project_id}
                                ).fetchone()

                                def _jsonify(val):
                                    if isinstance(val, (dict, list)):
                                        return json.dumps(val, ensure_ascii=False)
                                    return val

                                if existing:
                                    # 项目已存在，比较时间戳决定是否更新
                                    local_timestamp = max(project.created_at, project.updated_at or 0)
                                    external_timestamp = max(existing.created_at, existing.updated_at or 0)

                                    logger.info(f"� Comparing project {project.title} (ID: {project.project_id}):")
                                    logger.info(f"   Local timestamp: {local_timestamp}")
                                    logger.info(f"   External timestamp: {external_timestamp}")

                                    if local_timestamp > external_timestamp:
                                        # 本地数据更新，同步到外部
                                        external_conn.execute(
                                            text("""
                                                UPDATE projects SET
                                                    title = :title,
                                                    scenario = :scenario,
                                                    topic = :topic,
                                                    requirements = :requirements,
                                                    status = :status,
                                                    owner_id = :owner_id,
                                                    outline = :outline,
                                                    slides_html = :slides_html,
                                                    slides_data = :slides_data,
                                                    confirmed_requirements = :confirmed_requirements,
                                                    project_metadata = :project_metadata,
                                                    version = :version,
                                                    updated_at = :updated_at
                                                WHERE project_id = :project_id
                                            """),
                                            {
                                                "title": project.title,
                                                "scenario": project.scenario,
                                                "topic": project.topic,
                                                "requirements": project.requirements,
                                                "status": project.status,
                                                "owner_id": project.owner_id,
                                                "outline": _jsonify(project.outline),
                                                "slides_html": project.slides_html,
                                                "slides_data": _jsonify(project.slides_data),
                                                "confirmed_requirements": _jsonify(project.confirmed_requirements),
                                                "project_metadata": _jsonify(project.project_metadata),
                                                "version": project.version,
                                                "updated_at": project.updated_at or project.created_at,
                                                "project_id": project.project_id
                                            }
                                        )
                                        logger.info(f"📤 Updated project {project.title} (ID: {project.project_id}) in external database")
                                    elif local_timestamp == external_timestamp:
                                        logger.info(f"⏭️  Project {project.title} (ID: {project.project_id}) is already synchronized")
                                    else:
                                        logger.info(f"⏭️  External project {project.title} (ID: {project.project_id}) is newer, skipping local update")
                                else:
                                    # 项目不存在，插入新项目
                                    external_conn.execute(
                                        text("""
                                            INSERT INTO projects
                                            (project_id, title, scenario, topic, requirements, status, owner_id, outline, slides_html, slides_data, confirmed_requirements, project_metadata, version, created_at, updated_at)
                                            VALUES (:project_id, :title, :scenario, :topic, :requirements, :status, :owner_id, :outline, :slides_html, :slides_data, :confirmed_requirements, :project_metadata, :version, :created_at, :updated_at)
                                        """),
                                        {
                                            "project_id": project.project_id,
                                            "title": project.title,
                                            "scenario": project.scenario,
                                            "topic": project.topic,
                                            "requirements": project.requirements,
                                            "status": project.status,
                                            "owner_id": project.owner_id,
                                            "outline": _jsonify(project.outline),
                                            "slides_html": project.slides_html,
                                            "slides_data": _jsonify(project.slides_data),
                                            "confirmed_requirements": _jsonify(project.confirmed_requirements),
                                            "project_metadata": _jsonify(project.project_metadata),
                                            "version": project.version,
                                            "created_at": project.created_at,
                                            "updated_at": project.updated_at or project.created_at
                                        }
                                    )
                                    logger.info(f"📤 Inserted new project {project.title} (ID: {project.project_id}) to external database")

            # 在线程池中运行同步操作
            import asyncio
            await asyncio.to_thread(sync_presentations)

            logger.info("✅ Presentations sync local to external completed")

        except Exception as e:
            logger.error(f"❌ Presentations sync local to external failed: {e}")

    async def _sync_presentations_external_to_local(self):
        """同步外部演示文稿到本地数据库"""
        if not db_manager.external_engine:
            return

        try:
            logger.info("🔄 Syncing external presentations to local database...")

            # 获取增量同步的时间窗口
            cutoff_time = self.last_sync_time or (datetime.now() - timedelta(hours=24))

            def sync_presentations():
                from ..database.database import SessionLocal

                # 获取外部数据库中有变更的项目
                if db_manager.external_engine:
                    with db_manager.external_engine.connect() as external_conn:
                        changed_projects = external_conn.execute(
                            text("SELECT * FROM projects WHERE created_at > :cutoff OR updated_at > :cutoff"),
                            {"cutoff": cutoff_time.timestamp()}
                        ).fetchall()

                        if not changed_projects:
                            logger.info("📭 No external presentation changes to sync")
                            return

                        logger.info(f"� Found {len(changed_projects)} external presentations with changes")

                        # 同步到本地数据库
                        with SessionLocal() as local_session:
                            for project in changed_projects:
                                # 首先尝试通过project_id匹配项目
                                existing = local_session.execute(
                                    text("SELECT id, project_id, created_at, updated_at FROM projects WHERE project_id = :project_id"),
                                    {"project_id": project.project_id}
                                ).fetchone()


                                # --- 修复：dict/list 字段序列化为 JSON 字符串，兼容 SQLite ---
                                import json
                                def _jsonify(val):
                                    if isinstance(val, (dict, list)):
                                        return json.dumps(val, ensure_ascii=False)
                                    return val

                                update_params = {
                                    "title": project.title,
                                    "scenario": project.scenario,
                                    "topic": project.topic,
                                    "requirements": project.requirements,
                                    "status": project.status,
                                    "owner_id": project.owner_id,
                                    "outline": _jsonify(project.outline),
                                    "slides_html": project.slides_html,
                                    "slides_data": _jsonify(project.slides_data),
                                    "confirmed_requirements": _jsonify(project.confirmed_requirements),
                                    "project_metadata": _jsonify(project.project_metadata),
                                    "version": project.version,
                                    "updated_at": project.updated_at or project.created_at,
                                    "project_id": project.project_id
                                }

                                insert_params = {
                                    "project_id": project.project_id,
                                    "title": project.title,
                                    "scenario": project.scenario,
                                    "topic": project.topic,
                                    "requirements": project.requirements,
                                    "status": project.status,
                                    "owner_id": project.owner_id,
                                    "outline": _jsonify(project.outline),
                                    "slides_html": project.slides_html,
                                    "slides_data": _jsonify(project.slides_data),
                                    "confirmed_requirements": _jsonify(project.confirmed_requirements),
                                    "project_metadata": _jsonify(project.project_metadata),
                                    "version": project.version,
                                    "created_at": project.created_at,
                                    "updated_at": project.updated_at or project.created_at
                                }

                                if existing:
                                    # 项目已存在，比较时间戳决定是否更新
                                    external_timestamp = max(project.created_at, project.updated_at or 0)
                                    local_timestamp = max(existing.created_at, existing.updated_at or 0)

                                    # 如果外部是权威来源，则强制以外部为准（覆盖本地），否则按时间戳比较
                                    should_apply_external = (
                                        True if self.authoritative_source == "external" else external_timestamp > local_timestamp
                                    )

                                    if should_apply_external:
                                        # 外部数据更新，同步到本地
                                        local_session.execute(
                                            text("""
                                                UPDATE projects SET
                                                    title = :title,
                                                    scenario = :scenario,
                                                    topic = :topic,
                                                    requirements = :requirements,
                                                    status = :status,
                                                    owner_id = :owner_id,
                                                    outline = :outline,
                                                    slides_html = :slides_html,
                                                    slides_data = :slides_data,
                                                    confirmed_requirements = :confirmed_requirements,
                                                    project_metadata = :project_metadata,
                                                    version = :version,
                                                    updated_at = :updated_at
                                                WHERE project_id = :project_id
                                            """),
                                            update_params
                                        )
                                        logger.info(f"📥 Updated project {project.title} (ID: {project.project_id}) in local database")
                                    else:
                                        logger.info(f"⏭️  Local project {project.title} (ID: {project.project_id}) is already synchronized")
                                else:
                                    # 项目不存在，插入新项目
                                    local_session.execute(
                                        text("""
                                            INSERT INTO projects
                                            (project_id, title, scenario, topic, requirements, status, owner_id, outline, slides_html, slides_data, confirmed_requirements, project_metadata, version, created_at, updated_at)
                                            VALUES (:project_id, :title, :scenario, :topic, :requirements, :status, :owner_id, :outline, :slides_html, :slides_data, :confirmed_requirements, :project_metadata, :version, :created_at, :updated_at)
                                        """),
                                        insert_params
                                    )
                                    logger.info(f"📥 Inserted new project {project.title} (ID: {project.project_id}) to local database")

                            local_session.commit()

            # 在线程池中运行同步操作
            import asyncio
            await asyncio.to_thread(sync_presentations)

            logger.info("✅ Presentations sync external to local completed")

        except Exception as e:
            logger.error(f"❌ Presentations sync external to local failed: {e}")

    async def _sync_templates_local_to_external(self):
        """同步本地模板到外部数据库 (PPTTemplate + GlobalMasterTemplate)"""
        if not db_manager.external_engine:
            return
        try:
            logger.info("🔄 Syncing local templates to external database...")
            cutoff_time = self.last_sync_time or (datetime.now() - timedelta(hours=24))

            def do_sync():
                from ..database.database import SessionLocal
                with SessionLocal() as local_session:
                    # 项目级模板
                    changed_templates = local_session.execute(
                        text("SELECT * FROM ppt_templates WHERE created_at > :cutoff OR updated_at > :cutoff"),
                        {"cutoff": cutoff_time.timestamp()},
                    ).fetchall()

                    # 全局模板
                    changed_global = local_session.execute(
                        text("SELECT * FROM global_master_templates WHERE created_at > :cutoff OR updated_at > :cutoff"),
                        {"cutoff": cutoff_time.timestamp()},
                    ).fetchall()

                    if not changed_templates and not changed_global:
                        logger.info("📭 No local template changes to sync")
                        return

                    with db_manager.external_engine.connect() as external_conn:  # type: ignore[union-attr]
                        # 处理 ppt_templates
                        for tpl in changed_templates:
                            existing = external_conn.execute(
                                text("SELECT id, updated_at, created_at FROM ppt_templates WHERE id = :id"),
                                {"id": tpl.id},
                            ).fetchone()
                            local_ts = max(tpl.created_at, tpl.updated_at or 0)
                            if existing:
                                external_ts = max(existing.updated_at or 0, existing.created_at or 0)
                                if local_ts > external_ts:
                                    external_conn.execute(
                                        text(
                                            """
                                            UPDATE ppt_templates SET project_id=:project_id, template_type=:template_type, template_name=:template_name, description=:description, html_template=:html_template, applicable_scenarios=:applicable_scenarios, style_config=:style_config, usage_count=:usage_count, updated_at=:updated_at WHERE id=:id
                                            """
                                        ),
                                        {
                                            "project_id": tpl.project_id,
                                            "template_type": tpl.template_type,
                                            "template_name": tpl.template_name,
                                            "description": tpl.description,
                                            "html_template": tpl.html_template,
                                            "applicable_scenarios": tpl.applicable_scenarios,
                                            "style_config": tpl.style_config,
                                            "usage_count": tpl.usage_count,
                                            "updated_at": tpl.updated_at or tpl.created_at,
                                            "id": tpl.id,
                                        },
                                    )
                            else:
                                external_conn.execute(
                                    text(
                                        """
                                        INSERT INTO ppt_templates (id, project_id, template_type, template_name, description, html_template, applicable_scenarios, style_config, usage_count, created_at, updated_at)
                                        VALUES (:id, :project_id, :template_type, :template_name, :description, :html_template, :applicable_scenarios, :style_config, :usage_count, :created_at, :updated_at)
                                        """
                                    ),
                                    {
                                        "id": tpl.id,
                                        "project_id": tpl.project_id,
                                        "template_type": tpl.template_type,
                                        "template_name": tpl.template_name,
                                        "description": tpl.description,
                                        "html_template": tpl.html_template,
                                        "applicable_scenarios": tpl.applicable_scenarios,
                                        "style_config": tpl.style_config,
                                        "usage_count": tpl.usage_count,
                                        "created_at": tpl.created_at,
                                        "updated_at": tpl.updated_at or tpl.created_at,
                                    },
                                )

                        # 处理 global_master_templates
                        for g in changed_global:
                            existing = external_conn.execute(
                                text("SELECT id, updated_at, created_at FROM global_master_templates WHERE id = :id"),
                                {"id": g.id},
                            ).fetchone()
                            local_ts = max(g.created_at, g.updated_at or 0)
                            if existing:
                                external_ts = max(existing.updated_at or 0, existing.created_at or 0)
                                if local_ts > external_ts:
                                    external_conn.execute(
                                        text(
                                            """
                                            UPDATE global_master_templates SET template_name=:template_name, description=:description, html_template=:html_template, preview_image=:preview_image, style_config=:style_config, tags=:tags, is_default=:is_default, is_active=:is_active, usage_count=:usage_count, created_by=:created_by, updated_at=:updated_at WHERE id=:id
                                            """
                                        ),
                                        {
                                            "template_name": g.template_name,
                                            "description": g.description,
                                            "html_template": g.html_template,
                                            "preview_image": g.preview_image,
                                            "style_config": g.style_config,
                                            "tags": g.tags,
                                            # PostgreSQL 严格要求 boolean，SQLite 可能返回 0/1，统一转换
                                            "is_default": bool(g.is_default) if g.is_default is not None else False,
                                            "is_active": bool(g.is_active) if g.is_active is not None else True,
                                            "usage_count": g.usage_count,
                                            "created_by": g.created_by,
                                            "updated_at": g.updated_at or g.created_at,
                                            "id": g.id,
                                        },
                                    )
                            else:
                                external_conn.execute(
                                    text(
                                        """
                                        INSERT INTO global_master_templates (id, template_name, description, html_template, preview_image, style_config, tags, is_default, is_active, usage_count, created_by, created_at, updated_at)
                                        VALUES (:id, :template_name, :description, :html_template, :preview_image, :style_config, :tags, :is_default, :is_active, :usage_count, :created_by, :created_at, :updated_at)
                                        """
                                    ),
                                    {
                                        "id": g.id,
                                        "template_name": g.template_name,
                                        "description": g.description,
                                        "html_template": g.html_template,
                                        "preview_image": g.preview_image,
                                        "style_config": g.style_config,
                                        "tags": g.tags,
                                        # 显式转换，避免向 PostgreSQL 传 0/1 导致类型错误
                                        "is_default": bool(g.is_default) if g.is_default is not None else False,
                                        "is_active": bool(g.is_active) if g.is_active is not None else True,
                                        "usage_count": g.usage_count,
                                        "created_by": g.created_by,
                                        "created_at": g.created_at,
                                        "updated_at": g.updated_at or g.created_at,
                                    },
                                )

            import asyncio
            await asyncio.to_thread(do_sync)
            logger.info("✅ Templates sync local->external completed")
        except Exception as e:
            logger.error(f"❌ Templates sync local to external failed: {e}")

    async def _sync_templates_external_to_local(self):
        """同步外部模板到本地 (双向合并逻辑与项目/用户类似)"""
        if not db_manager.external_engine:
            return
        try:
            logger.info("🔄 Syncing external templates to local database...")
            cutoff_time = self.last_sync_time or (datetime.now() - timedelta(hours=24))

            def do_sync():
                from ..database.database import SessionLocal
                with SessionLocal() as local_session:
                    with db_manager.external_engine.connect() as external_conn:  # type: ignore[union-attr]
                        # ppt_templates
                        ext_templates = external_conn.execute(
                            text("SELECT * FROM ppt_templates WHERE created_at > :cutoff OR updated_at > :cutoff"),
                            {"cutoff": cutoff_time.timestamp()},
                        ).fetchall()
                        for tpl in ext_templates:
                            existing = local_session.execute(
                                text("SELECT id, created_at, updated_at FROM ppt_templates WHERE id = :id"),
                                {"id": tpl.id},
                            ).fetchone()
                            external_ts = max(tpl.updated_at or 0, tpl.created_at or 0)
                            if existing:
                                local_ts = max(existing.updated_at or 0, existing.created_at or 0)
                                if external_ts > local_ts:
                                    local_session.execute(
                                        text(
                                            """
                                            UPDATE ppt_templates SET project_id=:project_id, template_type=:template_type, template_name=:template_name, description=:description, html_template=:html_template, applicable_scenarios=:applicable_scenarios, style_config=:style_config, usage_count=:usage_count, updated_at=:updated_at WHERE id=:id
                                            """
                                        ),
                                        {
                                            "project_id": tpl.project_id,
                                            "template_type": tpl.template_type,
                                            "template_name": tpl.template_name,
                                            "description": tpl.description,
                                            "html_template": tpl.html_template,
                                            "applicable_scenarios": tpl.applicable_scenarios,
                                            "style_config": tpl.style_config,
                                            "usage_count": tpl.usage_count,
                                            "updated_at": tpl.updated_at or tpl.created_at,
                                            "id": tpl.id,
                                        },
                                    )
                            else:
                                local_session.execute(
                                    text(
                                        """
                                        INSERT INTO ppt_templates (id, project_id, template_type, template_name, description, html_template, applicable_scenarios, style_config, usage_count, created_at, updated_at)
                                        VALUES (:id, :project_id, :template_type, :template_name, :description, :html_template, :applicable_scenarios, :style_config, :usage_count, :created_at, :updated_at)
                                        """
                                    ),
                                    {
                                        "id": tpl.id,
                                        "project_id": tpl.project_id,
                                        "template_type": tpl.template_type,
                                        "template_name": tpl.template_name,
                                        "description": tpl.description,
                                        "html_template": tpl.html_template,
                                        "applicable_scenarios": tpl.applicable_scenarios,
                                        "style_config": tpl.style_config,
                                        "usage_count": tpl.usage_count,
                                        "created_at": tpl.created_at,
                                        "updated_at": tpl.updated_at or tpl.created_at,
                                    },
                                )

                        # global master templates
                        ext_global = external_conn.execute(
                            text("SELECT * FROM global_master_templates WHERE created_at > :cutoff OR updated_at > :cutoff"),
                            {"cutoff": cutoff_time.timestamp()},
                        ).fetchall()
                        for g in ext_global:
                            existing = local_session.execute(
                                text("SELECT id, created_at, updated_at FROM global_master_templates WHERE id = :id"),
                                {"id": g.id},
                            ).fetchone()
                            external_ts = max(g.updated_at or 0, g.created_at or 0)
                            if existing:
                                local_ts = max(existing.updated_at or 0, existing.created_at or 0)
                                if external_ts > local_ts:
                                    local_session.execute(
                                        text(
                                            """
                                            UPDATE global_master_templates SET template_name=:template_name, description=:description, html_template=:html_template, preview_image=:preview_image, style_config=:style_config, tags=:tags, is_default=:is_default, is_active=:is_active, usage_count=:usage_count, created_by=:created_by, updated_at=:updated_at WHERE id=:id
                                            """
                                        ),
                                        {
                                            "template_name": g.template_name,
                                            "description": g.description,
                                            "html_template": g.html_template,
                                            "preview_image": g.preview_image,
                                            "style_config": g.style_config,
                                            "tags": g.tags,
                                            # 统一布尔类型
                                            "is_default": bool(g.is_default) if g.is_default is not None else False,
                                            "is_active": bool(g.is_active) if g.is_active is not None else True,
                                            "usage_count": g.usage_count,
                                            "created_by": g.created_by,
                                            "updated_at": g.updated_at or g.created_at,
                                            "id": g.id,
                                        },
                                    )
                            else:
                                local_session.execute(
                                    text(
                                        """
                                        INSERT INTO global_master_templates (id, template_name, description, html_template, preview_image, style_config, tags, is_default, is_active, usage_count, created_by, created_at, updated_at)
                                        VALUES (:id, :template_name, :description, :html_template, :preview_image, :style_config, :tags, :is_default, :is_active, :usage_count, :created_by, :created_at, :updated_at)
                                        """
                                    ),
                                    {
                                        "id": g.id,
                                        "template_name": g.template_name,
                                        "description": g.description,
                                        "html_template": g.html_template,
                                        "preview_image": g.preview_image,
                                        "style_config": g.style_config,
                                        "tags": g.tags,
                                        # 统一布尔类型
                                        "is_default": bool(g.is_default) if g.is_default is not None else False,
                                        "is_active": bool(g.is_active) if g.is_active is not None else True,
                                        "usage_count": g.usage_count,
                                        "created_by": g.created_by,
                                        "created_at": g.created_at,
                                        "updated_at": g.updated_at or g.created_at,
                                    },
                                )
                        local_session.commit()

            import asyncio
            await asyncio.to_thread(do_sync)
            logger.info("✅ Templates sync external->local completed")
        except Exception as e:
            logger.error(f"❌ Templates sync external to local failed: {e}")

    async def _full_sync_local_to_external(self):
        """全量同步本地数据到外部数据库"""
        try:
            logger.info("🔄 Starting full sync from local to external...")

            # Note: User sync disabled as per requirements
            # await self._sync_users_local_to_external()

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

            # Note: User sync disabled as per requirements
            # await self._sync_users_external_to_local()

            # 同步所有演示文稿
            await self._sync_presentations_external_to_local()

            # 同步所有模板
            await self._sync_templates_external_to_local()

            logger.info("✅ Full sync external to local completed")

        except Exception as e:
            logger.error(f"❌ Full sync external to local failed: {e}")

    async def _get_users_from_r2_latest(self) -> List[Dict[str, Any]]:
        """从R2下载最新备份，解压并从其中的SQLite数据库提取 users 表为字典列表（启发式实现）。"""
        results: List[Dict[str, Any]] = []
        try:
            if not backup_service._is_r2_configured():
                logger.info("R2 未配置，跳过 R2 用户快照提取")
                return results

            # 列出R2备份文件并选择最新
            r2_files = await list_r2_files()
            if not r2_files:
                logger.info("R2 上没有备份文件")
                return results

            latest = r2_files[0]
            key = latest.get('key')
            if not key:
                return results

            tmp_dir = Path(tempfile.mkdtemp(prefix='r2_restore_'))
            try:
                from botocore.config import Config
                import boto3

                config = Config(region_name='auto')
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=backup_service.r2_config['access_key'],
                    aws_secret_access_key=backup_service.r2_config['secret_key'],
                    endpoint_url=backup_service.r2_config['endpoint'],
                    config=config
                )

                local_backup_path = tmp_dir / Path(key).name
                await asyncio.to_thread(s3_client.download_file, backup_service.r2_config['bucket'], key, str(local_backup_path))

                # 解压并查找 .db 文件
                with zipfile.ZipFile(str(local_backup_path), 'r') as zf:
                    db_members = [m for m in zf.namelist() if m.endswith('.db')]
                    if not db_members:
                        logger.info("R2 备份中未找到 .db 文件")
                        return results

                    extracted_db = tmp_dir / Path(db_members[0]).name
                    zf.extract(db_members[0], path=str(tmp_dir))
                    extracted_path = tmp_dir / db_members[0]
                    if extracted_path.exists():
                        shutil.move(str(extracted_path), str(extracted_db))

                    conn = sqlite3.connect(str(extracted_db))
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    try:
                        cur.execute('SELECT * FROM users')
                        rows = cur.fetchall()
                        for r in rows:
                            row = dict(r)
                            for k in ('created_at', 'updated_at', 'last_login'):
                                if k in row and row[k] is not None:
                                    try:
                                        row[k] = float(row[k])
                                    except Exception:
                                        pass
                            results.append(row)
                    finally:
                        conn.close()

            finally:
                try:
                    shutil.rmtree(str(tmp_dir))
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"_get_users_from_r2_latest failed: {e}")

        return results

    async def _sync_users_local_to_external_force(self):
        """强制将本地用户推送到外部，不受 authoritative_source 限制（仅用户表）。"""
        # Ensure external engine exists if DATABASE_URL is present but db_manager wasn't initialized
        if not getattr(db_manager, 'external_engine', None):
            try:
                if getattr(db_manager, 'external_url', None):
                    # Try creating backup/external engine on demand
                    db_manager._create_backup_engine()
                    db_manager.sync_enabled = True
                    logger.info("✅ Created external backup engine on demand for forced push")
            except Exception as e:
                logger.info(f"External engine not available (on-demand init failed): {e} - skipping forced push")
                return

        logger.info("🔁 Forcing local->external user sync (force mode)")

        def push_users():
            from ..database.database import SessionLocal

            with SessionLocal() as local_session:
                changed_users = local_session.execute(text("SELECT * FROM users")).fetchall()
                if not changed_users:
                    logger.info("📭 No local users to push")
                    return

                with db_manager.external_engine.connect() as external_conn:  # type: ignore[union-attr]
                    for user in changed_users:
                        try:
                            # Safer approach: if local has external_id, prefer updating by external id.
                            local_ext_id = getattr(user, 'external_id', None)
                            updated = False

                            if local_ext_id:
                                # Try update by external id
                                try:
                                    res = external_conn.execute(text("""
                                        UPDATE users SET
                                            username = :username,
                                            email = :email,
                                            password_hash = :password_hash,
                                            is_active = :is_active,
                                            is_admin = :is_admin,
                                            updated_at = :updated_at,
                                            last_login = :last_login
                                        WHERE id = :ext_id
                                    """), {
                                        "username": user.username,
                                        "email": user.email,
                                        "password_hash": user.password_hash,
                                        "is_active": bool(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else True,
                                        "is_admin": bool(user.is_admin),
                                        "updated_at": user.updated_at or user.created_at,
                                        "last_login": user.last_login,
                                        "ext_id": local_ext_id,
                                    })
                                    if getattr(res, 'rowcount', None) and res.rowcount > 0:
                                        updated = True
                                        logger.info(f"📤 Forced update to external user (by external_id={local_ext_id}) for local user {user.username}")
                                except Exception:
                                    try:
                                        external_conn.rollback()
                                    except Exception:
                                        pass

                            if not updated:
                                # If no external_id or update by id didn't match, probe external by username
                                row = external_conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": user.username}).fetchone()
                                if row:
                                    ext_id = row.id
                                    # If local has external_id and they mismatch, record conflict and skip
                                    if local_ext_id and local_ext_id != ext_id:
                                        from ..database.database import SessionLocal as _SessionLocal
                                        with _SessionLocal() as session:
                                            sc = SyncConflict(
                                                local_id=user.id,
                                                external_id=ext_id,
                                                attempted_username=user.username,
                                                reason="external_id_mismatch_on_update",
                                                payload={"local_external_id": local_ext_id, "found_external_id": ext_id}
                                            )
                                            session.add(sc)
                                            session.commit()
                                        logger.warning(f"⚠️ Conflict: local.external_id={local_ext_id} but external username={user.username} has id={ext_id} - recorded and skipped")
                                    else:
                                        # Safe to update the external row found by username
                                        external_conn.execute(text("""
                                            UPDATE users SET
                                                email = :email,
                                                password_hash = :password_hash,
                                                is_active = :is_active,
                                                is_admin = :is_admin,
                                                updated_at = :updated_at,
                                                last_login = :last_login
                                            WHERE id = :id
                                        """), {
                                            "email": user.email,
                                            "password_hash": user.password_hash,
                                            "is_active": bool(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else True,
                                            "is_admin": bool(user.is_admin),
                                            "updated_at": user.updated_at or user.created_at,
                                            "last_login": user.last_login,
                                            "id": ext_id,
                                        })
                                        logger.info(f"📤 Forced update to external user {user.username} (matched by username id={ext_id})")
                                        # record mapping if local had none
                                        if not local_ext_id:
                                            try:
                                                from ..database.database import SessionLocal as _SessionLocal
                                                with _SessionLocal() as session:
                                                    session.execute(text("UPDATE users SET external_id = :ext WHERE id = :id"), {"ext": ext_id, "id": user.id})
                                                    session.commit()
                                            except Exception:
                                                pass
                                else:
                                    # No external row with same username — attempt INSERT and capture returning id if supported
                                    try:
                                        # Try INSERT with RETURNING id for Postgres-compatible DBs
                                        try:
                                            res = external_conn.execute(text("""
                                                INSERT INTO users (username, email, password_hash, is_active, is_admin, created_at, updated_at, last_login)
                                                VALUES (:username, :email, :password_hash, :is_active, :is_admin, :created_at, :updated_at, :last_login)
                                                RETURNING id
                                            """), {
                                                "username": user.username,
                                                "email": user.email,
                                                "password_hash": user.password_hash,
                                                "is_active": bool(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else True,
                                                "is_admin": bool(user.is_admin),
                                                "created_at": user.created_at,
                                                "updated_at": user.updated_at or user.created_at,
                                                "last_login": user.last_login
                                            })
                                            new_id_row = res.fetchone() if res is not None else None
                                            new_ext_id = new_id_row[0] if new_id_row else None
                                        except Exception:
                                            # Fallback to plain INSERT (no returning)
                                            external_conn.execute(text("""
                                                INSERT INTO users (username, email, password_hash, is_active, is_admin, created_at, updated_at, last_login)
                                                VALUES (:username, :email, :password_hash, :is_active, :is_admin, :created_at, :updated_at, :last_login)
                                            """), {
                                                "username": user.username,
                                                "email": user.email,
                                                "password_hash": user.password_hash,
                                                "is_active": bool(user.is_active) if hasattr(user, 'is_active') and user.is_active is not None else True,
                                                "is_admin": bool(user.is_admin),
                                                "created_at": user.created_at,
                                                "updated_at": user.updated_at or user.created_at,
                                                "last_login": user.last_login
                                            })
                                            new_ext_id = None

                                        logger.info(f"📤 Forced insert to external user {user.username} (id assigned by external DB: {new_ext_id})")
                                        # If we got a new external id, store it back to local user record
                                        if new_ext_id:
                                            try:
                                                from ..database.database import SessionLocal as _SessionLocal
                                                with _SessionLocal() as session:
                                                    session.execute(text("UPDATE users SET external_id = :ext WHERE id = :id"), {"ext": new_ext_id, "id": user.id})
                                                    session.commit()
                                            except Exception:
                                                pass
                                    except IntegrityError as ie_insert:
                                        # If duplicate key on insert (race), record conflict and skip
                                        try:
                                            external_conn.rollback()
                                        except Exception:
                                            pass
                                        from ..database.database import SessionLocal as _SessionLocal
                                        with _SessionLocal() as session:
                                            sc = SyncConflict(
                                                local_id=user.id,
                                                external_id=None,
                                                attempted_username=user.username,
                                                reason="integrity_error_on_forced_insert",
                                                payload={"error": str(ie_insert)}
                                            )
                                            session.add(sc)
                                            session.commit()
                                        logger.warning(f"⚠️ IntegrityError when inserting external user {user.username}: {ie_insert} - recorded to sync_conflicts and skipped")

                        except Exception as e:
                            try:
                                external_conn.rollback()
                            except Exception:
                                pass
                            from ..database.database import SessionLocal as _SessionLocal
                            with _SessionLocal() as session:
                                sc = SyncConflict(
                                    local_id=user.id,
                                    external_id=None,
                                    attempted_username=user.username,
                                    reason="error_on_forced_push",
                                    payload={"error": str(e)}
                                )
                                session.add(sc)
                                session.commit()
                            logger.warning(f"⚠️ Error forcing user {user.username} to external: {e} - recorded to sync_conflicts and skipped")

                    try:
                        external_conn.commit()
                    except Exception:
                        try:
                            external_conn.rollback()
                        except Exception:
                            pass

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            await asyncio.get_event_loop().run_in_executor(executor, push_users)

        logger.info("🔁 Forced local->external user sync completed")
        # After forcing inserts/updates, also propagate deletions safely (soft-delete external users missing locally)
        try:
            if not db_manager.external_engine:
                logger.info("External engine not available - skipping forced deletion propagation")
                return

            def propagate_deletes():
                from ..database.database import SessionLocal

                with db_manager.external_engine.connect() as external_conn:  # type: ignore[union-attr]
                    with SessionLocal() as local_session:
                        all_external = external_conn.execute(text("SELECT id, username FROM users")).fetchall()
                        external_usernames = {r.username for r in all_external}
                        local_usernames = {u.username for u in local_session.execute(text("SELECT username FROM users")).fetchall()}

                        usernames_to_delete = external_usernames - local_usernames
                        if not usernames_to_delete:
                            return

                        logger.info(f"🗑️ Forced sync: propagating deletion of {len(usernames_to_delete)} users to external DB (hard-delete)")
                        for uname in usernames_to_delete:
                            try:
                                row = external_conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": uname}).fetchone()
                                if not row:
                                    continue
                                ext_id = row.id
                                try:
                                    # Hard delete: remove sessions first to avoid FK violations
                                    try:
                                        external_conn.execute(text("DELETE FROM user_sessions WHERE user_id = :id"), {"id": ext_id})
                                    except Exception:
                                        pass
                                    external_conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": ext_id})
                                    logger.info(f"🗑️ Hard-deleted external user id={ext_id} username={uname}")
                                except Exception as e:
                                    try:
                                        external_conn.rollback()
                                    except Exception:
                                        pass
                                    from ..database.database import SessionLocal as _SessionLocal
                                    with _SessionLocal() as session:
                                        sc = SyncConflict(
                                            local_id=None,
                                            external_id=ext_id,
                                            attempted_username=uname,
                                            reason="error_on_hard_delete_external",
                                            payload={"error": str(e)}
                                        )
                                        session.add(sc)
                                        session.commit()
                                    logger.warning(f"⚠️ Failed to hard-delete external user username={uname}: {e} - recorded to sync_conflicts")
                            except Exception as e:
                                try:
                                    external_conn.rollback()
                                except Exception:
                                    pass
                                from ..database.database import SessionLocal as _SessionLocal
                                with _SessionLocal() as session:
                                    sc = SyncConflict(
                                        local_id=None,
                                        external_id=None,
                                        attempted_username=uname,
                                        reason="error_on_delete_external",
                                        payload={"error": str(e)}
                                    )
                                    session.add(sc)
                                    session.commit()
                                logger.warning(f"⚠️ Failed to delete external user username={uname}: {e} - recorded to sync_conflicts")
                        # commit deletions performed in this external_conn
                        try:
                            external_conn.commit()
                        except Exception as e:
                            try:
                                external_conn.rollback()
                            except Exception:
                                pass
                            from ..database.database import SessionLocal as _SessionLocal
                            with _SessionLocal() as session:
                                sc = SyncConflict(
                                    local_id=None,
                                    external_id=None,
                                    attempted_username=None,
                                    reason="error_on_commit_external_deletes",
                                    payload={"error": str(e)}
                                )
                                session.add(sc)
                                session.commit()
                            logger.warning(f"⚠️ Failed to commit deletions to external DB: {e} - recorded to sync_conflicts")
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor() as _ex:
                await asyncio.get_event_loop().run_in_executor(_ex, propagate_deletes)

            # Note: propagate_deletes executes DELETEs inside its connection; ensure any open transactions are flushed.
            try:
                # no-op here: the propagate_deletes function uses its own external_conn and commits internally when needed.
                pass
            except Exception:
                # nothing to do
                pass

        except Exception as e:
            logger.warning(f"⚠️ Forced push deletion propagation failed: {e}")

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

    # ---------------- 新增：配置文件同步 ----------------
    def _ensure_external_config_table(self):
        """在外部数据库创建配置文件存储表 (flowslide_config_files)。"""
        if not db_manager.external_engine:
            return
        ddl_postgres = (
            "CREATE TABLE IF NOT EXISTS flowslide_config_files ("
            " name TEXT PRIMARY KEY,"
            " checksum TEXT,"
            " file_mtime DOUBLE PRECISION,"
            " content BYTEA NOT NULL,"
            " updated_at TIMESTAMP DEFAULT NOW()"
            ")"
        )
        ddl_generic = (
            "CREATE TABLE IF NOT EXISTS flowslide_config_files ("
            " name VARCHAR(255) PRIMARY KEY,"
            " checksum VARCHAR(128),"
            " file_mtime DOUBLE,"
            " content LONGBLOB NOT NULL,"
            " updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        try:
            dialect = db_manager.external_engine.dialect.name
        except Exception:
            dialect = "generic"
        ddl = ddl_postgres if dialect == "postgresql" else ddl_generic
        try:
            with db_manager.external_engine.begin() as conn:
                conn.exec_driver_sql(ddl)
        except Exception as e:
            logger.warning(f"⚠️ Failed creating flowslide_config_files table: {e}")

    def _collect_local_config_files(self) -> List[Path]:
        """收集需要同步的配置文件列表.

        策略：
          1. 根目录 *.json 中与部署/AI/用户设置相关的轻量文件 (大小 < 256KB)
          2. src/config/**/*.json 及 src/flowslide/config/**/*.json
          3. 排除备份、临时、node_modules、.git、backups 目录
        """
        patterns = [
            Path("."),
            Path("src/config"),
            Path("src/flowslide/config"),
        ]
        result: List[Path] = []
        seen = set()
        for base in patterns:
            if not base.exists():
                continue
            for p in base.rglob("*.json"):
                # 过滤无关或大型文件
                if any(part in {"node_modules", ".git", "backups", "temp"} for part in p.parts):
                    continue
                try:
                    if p.stat().st_size > 256 * 1024:  # 避免同步过大文件
                        continue
                except Exception:
                    continue
                name = p.as_posix()
                if name not in seen:
                    seen.add(name)
                    result.append(p)
        # 追加: 根目录 .env 也纳入同步（与用户需求一致：.env 同步与恢复）
        try:
            env_path = Path('.env')
            if env_path.exists() and env_path.is_file():
                size_ok = True
                try:
                    if env_path.stat().st_size > 128 * 1024:  # 限制 128KB
                        size_ok = False
                except Exception:
                    pass
                if size_ok and env_path.as_posix() not in seen:
                    result.append(env_path)
                    seen.add(env_path.as_posix())
        except Exception:
            pass
        return result

    # === 环境变量白名单 & 过滤逻辑 ===
    # 直接返回原始内容（取消任何 .env 脱敏/白名单逻辑）
    def _filter_env_content(self, content: bytes) -> bytes:  # 保留函数签名供调用处兼容
        return content

    def _calc_file_checksum(self, path: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        try:
            with path.open("rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    async def _sync_configs_local_to_external(self):
        """将本地配置文件(upsert)同步到外部数据库 flowslide_config_files 表。"""
        if not db_manager.external_engine:
            return
        try:
            self._ensure_external_config_table()
            files = self._collect_local_config_files()
            if not files:
                logger.debug("ℹ️ No local config files collected for sync")
                return

            # 读取外部已有的 checksum
            external_map = {}
            try:
                assert db_manager.external_engine is not None  # type: ignore[assert-type]
                with db_manager.external_engine.connect() as conn:  # type: ignore[union-attr]
                    # 先显式开启一个独立事务用于读取（某些驱动默认 autocommit=False 时异常会留下 aborted 状态）
                    read_trans = None
                    try:
                        read_trans = conn.begin()
                    except Exception:
                        read_trans = None
                    # 尝试增加 file_mtime 列（如果旧版本表无此列）
                    try:
                        conn.exec_driver_sql("ALTER TABLE flowslide_config_files ADD COLUMN file_mtime DOUBLE PRECISION")
                    except Exception:
                        try:
                            conn.exec_driver_sql("ALTER TABLE flowslide_config_files ADD COLUMN file_mtime DOUBLE")
                        except Exception:
                            pass
                    try:
                        rows = conn.execute(text("SELECT name, checksum, file_mtime, updated_at FROM flowslide_config_files")).fetchall()
                    except Exception as read_err:
                        # 若读取失败尝试回滚事务并重试一次
                        try:
                            if read_trans is not None:
                                read_trans.rollback()
                        except Exception:
                            pass
                        try:
                            rows = conn.execute(text("SELECT name, checksum, file_mtime, updated_at FROM flowslide_config_files")).fetchall()
                        except Exception:
                            raise read_err
                    finally:
                        try:
                            if read_trans is not None and read_trans.is_active:
                                read_trans.commit()
                        except Exception:
                            pass
                    for r in rows:
                        try:
                            external_map[r.name] = {"checksum": r.checksum, "updated_at": r.updated_at, "file_mtime": getattr(r, 'file_mtime', None)}
                        except Exception:
                            d = dict(r)
                            external_map[d.get("name")] = {"checksum": d.get("checksum"), "updated_at": d.get("updated_at"), "file_mtime": d.get("file_mtime")}
            except Exception as e:
                logger.warning(f"⚠️ Failed to read external config table: {e}")

            to_upsert = []
            for f in files:
                checksum = self._calc_file_checksum(f)
                rel_name = f.as_posix()
                existing = external_map.get(rel_name)
                try:
                    local_mtime = f.stat().st_mtime
                except Exception:
                    local_mtime = None
                # 若外部存在 且 (checksum 相同 或 外部 file_mtime >= 本地 mtime) 则跳过
                if existing:
                    ext_checksum = existing.get("checksum")
                    ext_mtime = existing.get("file_mtime")
                    if ext_checksum == checksum or (ext_mtime and local_mtime and ext_mtime >= local_mtime):
                        continue
                try:
                    content_bytes = f.read_bytes()
                except Exception as e:
                    logger.warning(f"⚠️ Skip config file {rel_name}, read error: {e}")
                    continue
                # .env 不再做脱敏过滤，直接同步
                to_upsert.append((rel_name, checksum, content_bytes, local_mtime))

            if not to_upsert:
                logger.info("📁 Config sync: no changed config files to upsert")
                return

            logger.info(f"📁 Config sync: upserting {len(to_upsert)} config files to external DB")

            engine = db_manager.external_engine
            dialect = engine.dialect.name.lower() if engine else ""
            # 预构建方言特定语句
            pg_stmt = text("""
                INSERT INTO flowslide_config_files (name, checksum, file_mtime, content, updated_at)
                VALUES (:name, :checksum, :file_mtime, :content, NOW())
                ON CONFLICT (name) DO UPDATE SET checksum = EXCLUDED.checksum, file_mtime = EXCLUDED.file_mtime, content = EXCLUDED.content, updated_at = NOW()
            """)
            mysql_stmt = text("""
                INSERT INTO flowslide_config_files (name, checksum, file_mtime, content, updated_at)
                VALUES (:name, :checksum, :file_mtime, :content, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE checksum = VALUES(checksum), file_mtime = VALUES(file_mtime), content = VALUES(content), updated_at = CURRENT_TIMESTAMP
            """)

            use_stmt = pg_stmt if 'postgres' in dialect else mysql_stmt if dialect in ('mysql','mariadb') else None

            with engine.connect() as conn:  # type: ignore[union-attr]
                # 对于 Postgres，单条失败会使事务 abort，改为逐条独立事务提交，避免整体失败
                if 'postgres' in dialect:
                    for name, checksum, content, file_mtime in to_upsert:
                        params = {"name": name, "checksum": checksum, "content": content, "file_mtime": file_mtime}
                        try:
                            trans = conn.begin()
                            try:
                                if use_stmt is not None:
                                    conn.execute(use_stmt, params)
                                else:
                                    conn.execute(pg_stmt, params)
                                trans.commit()
                            except Exception:
                                trans.rollback()
                                raise
                        except Exception as e_up:
                            logger.warning(f"⚠️ Upsert config file {name} failed (isolated): {e_up}")
                            continue
                else:
                    trans = conn.begin()
                    for name, checksum, content, file_mtime in to_upsert:
                        params = {"name": name, "checksum": checksum, "content": content, "file_mtime": file_mtime}
                        try:
                            if use_stmt is not None:
                                conn.execute(use_stmt, params)
                            else:
                                # 尝试双语法
                                try:
                                    conn.execute(pg_stmt, params)
                                except Exception:
                                    conn.execute(mysql_stmt, params)
                        except Exception as e_up:
                            logger.warning(f"⚠️ Upsert config file {name} failed (will continue): {e_up}")
                            # 非 Postgres 继续复用事务（MySQL 不会进入 failed 状态阻塞后续）
                            continue
                    try:
                        trans.commit()
                    except Exception as final_err:
                        try:
                            trans.rollback()
                        except Exception:
                            pass
                        logger.warning(f"⚠️ Final commit of config upserts failed: {final_err}")
            logger.info("✅ Config files sync local->external completed")
        except Exception as e:
            logger.error(f"❌ Config sync local->external failed: {e}")

    async def _sync_configs_external_to_local(self):
        """从外部数据库获取配置文件并写回本地（覆盖）。"""
        if not db_manager.external_engine:
            return
        try:
            self._ensure_external_config_table()
            assert db_manager.external_engine is not None  # type: ignore[assert-type]
            with db_manager.external_engine.connect() as conn:  # type: ignore[union-attr]
                rows = conn.execute(text("SELECT name, checksum, file_mtime, content FROM flowslide_config_files")).fetchall()
                if not rows:
                    logger.info("ℹ️ No config files found in external DB")
                    return
                restored = 0
                for r in rows:
                    try:
                        name = r.name if hasattr(r, 'name') else r[0]
                        file_mtime = getattr(r, 'file_mtime', None) if hasattr(r, 'file_mtime') else (r[2] if len(r) > 2 else None)
                        content = r.content if hasattr(r, 'content') else r[3]
                        target = Path(name)
                        # .env 直接覆盖（用户明确要求完全明文同步）
                        target.parent.mkdir(parents=True, exist_ok=True)
                        existing_bytes = None
                        try:
                            if target.exists():
                                existing_bytes = target.read_bytes()
                                # 若外部文件时间戳不比本地新，且校验和一致则跳过
                                if file_mtime and target.stat().st_mtime >= float(file_mtime):
                                    # checksum 比较（快速避免重写）
                                    import hashlib
                                    if existing_bytes:
                                        h = hashlib.sha256(existing_bytes).hexdigest()
                                        if h == getattr(r, 'checksum', None):
                                            continue
                        except Exception:
                            existing_bytes = None
                        if existing_bytes == content:
                            continue
                        target.write_bytes(content)
                        # 尝试恢复原始修改时间（不是关键，如失败可忽略）
                        try:
                            if file_mtime:
                                os.utime(target, (file_mtime, file_mtime))
                        except Exception:
                            pass
                        restored += 1
                    except Exception as ie:
                        logger.warning(f"⚠️ Fail write config file from external {r}: {ie}")
                logger.info(f"✅ Config files restored from external DB: {restored} updated")
        except Exception as e:
            logger.error(f"❌ Config sync external->local failed: {e}")

    def trigger_user_sync_background(self, direction: str = "local_to_external") -> None:
        """Trigger a user-only sync in a background thread to avoid blocking the caller.

        NOTE: User synchronization is DISABLED as per requirements.
        This method now does nothing to prevent user data syncing between local/external/R2.

        direction: 'local_to_external' or 'external_to_local' or 'both'
        """
        logger.info("ℹ️ User synchronization is disabled - no action taken")
        # User sync is disabled - do nothing
        return


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

