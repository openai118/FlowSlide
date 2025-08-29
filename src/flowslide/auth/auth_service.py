"""
Authentication service for FlowSlide
"""

import secrets
import time
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..core.simple_config import app_config
from ..database.models import User, UserSession


class AuthService:
    """Authentication service"""

    def __init__(self):
        self.session_expire_minutes = app_config.access_token_expire_minutes

    def _get_current_expire_minutes(self) -> int:
        """Get current session expire minutes from config (for real-time updates)"""
        return app_config.access_token_expire_minutes

    def create_user(
        self,
        db: Session,
        username: str,
        password: str,
        email: Optional[str] = None,
        is_admin: bool = False,
    ) -> User:
        """Create a new user"""
        # Check if user already exists in local database
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise ValueError("用户名已存在")

        if email:
            existing_email = db.query(User).filter(User.email == email).first()
            if existing_email:
                raise ValueError("邮箱已存在")

        # Check if user exists in external database
        from ..database.database import db_manager
        if db_manager.external_engine:
            try:
                with db_manager.external_engine.connect() as external_conn:
                    from sqlalchemy import text
                    result = external_conn.execute(
                        text("SELECT id, username FROM users WHERE username = :username"),
                        {"username": username}
                    ).fetchone()

                    if result:
                        raise ValueError(f"用户名 '{username}' 在外部数据库中已存在，无法创建本地用户")
            except ValueError:
                # 重新抛出用户名冲突错误
                raise
            except Exception as e:
                # 如果外部数据库连接失败，为了数据一致性，阻止创建
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"无法检查外部数据库中的用户名冲突: {e}")
                raise ValueError("无法验证用户名唯一性，请稍后重试或联系管理员")

        # Create new user
        user = User(username=username, email=email, is_admin=is_admin)
        user.set_password(password)

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    def authenticate_user(self, db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        user = (
            db.query(User).filter(and_(User.username == username, User.is_active == True)).first()
        )

        if user and user.check_password(password):
            # Update last login time
            user.last_login = time.time()
            db.commit()
            return user

        return None

    def create_session(self, db: Session, user: User) -> str:
        """Create a new session for user"""
        # Generate session ID
        session_id = secrets.token_urlsafe(64)

        # Get current expire minutes (for real-time config updates)
        current_expire_minutes = self._get_current_expire_minutes()

        # Calculate expiration time
        # If session_expire_minutes is 0, set to a very far future date (never expire)
        if current_expire_minutes == 0:
            # Set expiration to year 2099 (effectively never expires)
            expires_at = time.mktime(time.strptime("2099-12-31 23:59:59", "%Y-%m-%d %H:%M:%S"))
        else:
            expires_at = time.time() + (current_expire_minutes * 60)

        # Create session record
        session = UserSession(session_id=session_id, user_id=user.id, expires_at=expires_at)

        db.add(session)
        db.commit()

        return session_id

    def get_user_by_session(self, db: Session, session_id: str) -> Optional[User]:
        """Get user by session ID"""
        session = (
            db.query(UserSession)
            .filter(and_(UserSession.session_id == session_id, UserSession.is_active == True))
            .first()
        )

        if not session or session.is_expired():
            if session:
                # Mark session as inactive
                session.is_active = False
                db.commit()
            return None

        return session.user

    def logout_user(self, db: Session, session_id: str) -> bool:
        """Logout user by deactivating session"""
        session = db.query(UserSession).filter(UserSession.session_id == session_id).first()

        if session:
            session.is_active = False
            db.commit()
            return True

        return False

    def cleanup_expired_sessions(self, db: Session) -> int:
        """Clean up expired sessions"""
        current_time = time.time()
        # Don't clean up sessions that are set to never expire (year 2099 or later)
        year_2099_timestamp = time.mktime(time.strptime("2099-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"))

        expired_sessions = (
            db.query(UserSession)
            .filter(
                and_(
                    UserSession.expires_at < current_time,
                    UserSession.expires_at < year_2099_timestamp,  # Exclude never-expire sessions
                )
            )
            .all()
        )

        count = len(expired_sessions)
        for session in expired_sessions:
            session.is_active = False

        db.commit()
        return count

    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(and_(User.id == user_id, User.is_active == True)).first()

    def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        """Get user by username"""
        return (
            db.query(User).filter(and_(User.username == username, User.is_active == True)).first()
        )

    def update_user_password(self, db: Session, user: User, new_password: str) -> bool:
        """Update user password"""
        try:
            user.set_password(new_password)
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False

    def deactivate_user(self, db: Session, user: User) -> bool:
        """Deactivate user account"""
        try:
            user.is_active = False
            # Deactivate all user sessions
            sessions = db.query(UserSession).filter(UserSession.user_id == user.id).all()
            for session in sessions:
                session.is_active = False
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False

    def list_users(self, db: Session, skip: int = 0, limit: int = 100) -> list[User]:
        """List all users"""
        return db.query(User).offset(skip).limit(limit).all()

    def get_user_sessions(self, db: Session, user: User) -> list[UserSession]:
        """Get all active sessions for a user"""
        return (
            db.query(UserSession)
            .filter(and_(UserSession.user_id == user.id, UserSession.is_active == True))
            .all()
        )

    def update_user_info(
        self, db: Session, user: User, username: Optional[str] = None, email: Optional[str] = None
    ) -> bool:
        """Update user's basic info (username/email) with uniqueness checks"""
        try:
            if username and username != user.username:
                exists = db.query(User).filter(User.username == username).first()
                if exists:
                    raise ValueError("用户名已存在")
                user.username = username
            if email is not None and email != user.email:
                if email:
                    exists = db.query(User).filter(User.email == email).first()
                    if exists:
                        raise ValueError("邮箱已存在")
                user.email = email
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

    def delete_user_by_id(self, db: Session, user_id: int) -> bool:
        """Hard delete a user by id (admin only)"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            # Delete sessions
            db.query(UserSession).filter(UserSession.user_id == user_id).delete()
            # Delete user
            db.delete(user)
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False


# Global auth service instance
auth_service = AuthService()


def get_auth_service() -> AuthService:
    """Get auth service instance"""
    return auth_service


def init_default_admin(db: Session) -> None:
    """Initialize default admin user if no users exist"""
    import os
    from urllib.parse import urlparse
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    user_count = db.query(User).count()

    if user_count == 0:
        # 首先尝试从外部数据库同步用户
        database_url = os.getenv("DATABASE_URL", "")
        external_users = []

        if database_url:
            try:
                print("🔄 尝试从外部数据库同步用户...")

                # 创建外部数据库连接 - 移除pgbouncer特定参数
                if 'supabase' in database_url:
                    # 对于Supabase，修改URL以明确使用psycopg2
                    sync_url = database_url.replace('postgresql://', 'postgresql+psycopg2://')

                    # 移除pgbouncer特定参数
                    from urllib.parse import urlparse, urlunparse
                    parsed = urlparse(sync_url)
                    if parsed.query:
                        # 移除statement_cache_size和prepared_statement_cache_size参数
                        query_params = parsed.query.split('&')
                        filtered_params = [p for p in query_params if not p.startswith('statement_cache_size=') and not p.startswith('prepared_statement_cache_size=')]
                        new_query = '&'.join(filtered_params)
                        sync_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
                else:
                    sync_url = database_url.replace('postgresql://', 'postgresql+psycopg2://')

                connect_args = {}  # 不使用任何特殊参数

                external_engine = create_engine(
                    sync_url,
                    pool_size=1,
                    max_overflow=0,
                    pool_pre_ping=True,
                    echo=False,
                    connect_args=connect_args
                )

                # 创建会话
                ExternalSession = sessionmaker(bind=external_engine)
                external_db = ExternalSession()

                try:
                    # 首先检查数据库结构
                    print("🔍 检查外部数据库结构...")

                    # 获取所有表名
                    try:
                        tables_result = external_db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
                        tables = tables_result.fetchall()
                        table_names = [table[0] for table in tables]
                        print(f"   找到的表: {table_names}")

                        # 检查是否有用户相关的表
                        user_tables = [t for t in table_names if 'user' in t.lower()]
                        if user_tables:
                            print(f"   用户相关表: {user_tables}")
                        else:
                            print("   ⚠️ 没有找到用户相关的表")
                    except Exception as e:
                        print(f"   无法获取表信息: {e}")

                    # 查询外部数据库中的用户 - 尝试多种可能的表名和字段名
                    possible_queries = [
                        # 标准FlowSlide表结构
                        "SELECT username, email, password_hash, is_admin FROM users WHERE is_active = true",
                        "SELECT username, email, password, is_admin FROM users WHERE is_active = true",
                        "SELECT username, email, password_hash, is_admin FROM users WHERE is_active = 1",
                        "SELECT username, email, password, is_admin FROM users WHERE is_active = 1",
                        "SELECT username, email, password_hash, is_admin FROM users",
                        "SELECT username, email, password, is_admin FROM users",

                        # 可能的其他字段名
                        "SELECT username, email, password_hash, admin FROM users WHERE active = true",
                        "SELECT username, email, password, admin FROM users WHERE active = true",
                        "SELECT username, email, password_hash, admin FROM users WHERE active = 1",
                        "SELECT username, email, password, admin FROM users WHERE active = 1",

                        # 可能的其他表名
                        "SELECT username, email, password_hash, is_admin FROM user WHERE is_active = true",
                        "SELECT username, email, password, is_admin FROM user WHERE is_active = true",
                        "SELECT username, email, password_hash, is_admin FROM user",
                        "SELECT username, email, password, is_admin FROM user",

                        # 可能的字段顺序不同
                        "SELECT username, password_hash, email, is_admin FROM users WHERE is_active = true",
                        "SELECT username, password, email, is_admin FROM users WHERE is_active = true",
                    ]

                    external_users = []
                    successful_query = None

                    for query in possible_queries:
                        try:
                            result = external_db.execute(text(query))
                            users_data = result.fetchall()
                            if users_data and len(users_data) > 0:
                                external_users = users_data
                                successful_query = query
                                print(f"✅ 使用查询成功找到用户: {query}")
                                print(f"   找到 {len(external_users)} 个用户记录")
                                break
                        except Exception as e:
                            # 只在调试时显示错误
                            if "DEBUG" in os.environ:
                                print(f"   查询失败: {query} - {e}")
                            continue

                    if external_users and successful_query:
                        print(f"📋 从外部数据库找到 {len(external_users)} 个用户")

                        # 在本地数据库中创建这些用户
                        synced_count = 0
                        for user_data in external_users:
                            try:
                                # 处理不同格式的用户数据
                                if len(user_data) >= 4:
                                    # 尝试不同的字段顺序
                                    if "password_hash" in successful_query or "password" in successful_query:
                                        if "email" in successful_query and successful_query.find("email") < successful_query.find("password"):
                                            # username, email, password, is_admin
                                            username, email, password_hash, is_admin = user_data[:4]
                                        else:
                                            # username, password, email, is_admin
                                            username, password_hash, email, is_admin = user_data[:4]
                                    else:
                                        # 跳过格式不正确的记录
                                        continue

                                    # 确保数据类型正确
                                    username = str(username) if username else ""
                                    email = str(email) if email else ""
                                    password_hash = str(password_hash) if password_hash else ""
                                    is_admin = bool(is_admin) if is_admin is not None else False

                                    if not username or not password_hash:
                                        print(f"⚠️ 用户数据不完整，跳过: {user_data}")
                                        continue

                                    # 检查用户是否已存在
                                    existing_user = db.query(User).filter(User.username == username).first()
                                    if not existing_user:
                                        # 创建新用户，使用外部数据库的密码哈希
                                        user = User(
                                            username=username,
                                            email=email,
                                            is_admin=is_admin
                                        )
                                        # 直接设置密码哈希而不是通过set_password
                                        user.password_hash = password_hash

                                        db.add(user)
                                        synced_count += 1
                                        print(f"✅ 同步用户: {username} (管理员: {is_admin})")
                                    else:
                                        print(f"⚠️ 用户已存在，跳过: {username}")
                                else:
                                    print(f"⚠️ 用户数据字段数量不足: {user_data}")
                            except Exception as e:
                                print(f"⚠️ 同步用户失败: {e} - 数据: {user_data}")
                                continue

                        if synced_count > 0:
                            db.commit()
                            print(f"🎉 成功同步 {synced_count} 个用户！")
                            external_db.close()
                            external_engine.dispose()
                            return
                        else:
                            print("⚠️ 没有成功同步任何用户")
                    else:
                        print("📭 外部数据库中没有找到用户数据")
                        print("   尝试的查询可能都不匹配数据库结构")

                except Exception as e:
                    print(f"⚠️ 从外部数据库同步用户失败: {e}")
                    print("   可能的原因: 表名不正确、字段名不匹配、权限不足等")
                finally:
                    try:
                        external_db.close()
                        external_engine.dispose()
                    except:
                        pass

            except Exception as e:
                print(f"⚠️ 连接外部数据库失败: {e}")

        # 如果没有外部用户或同步失败，使用默认凭据
        print("📝 使用默认管理员凭据...")

        default_username = app_config.admin_username or "admin"
        default_password = app_config.admin_password or "admin123456"
        default_email = app_config.admin_email

        try:
            auth_service.create_user(
                db=db,
                username=default_username,
                password=default_password,
                email=default_email,
                is_admin=True,
            )
            print(f"✅ 默认管理员账户已创建: {default_username}")
            print("⚠️ 请及时修改默认密码！")
        except Exception as e:
            print(f"❌ 创建默认管理员账户失败: {e}")


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.verify(password, hashed)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False
