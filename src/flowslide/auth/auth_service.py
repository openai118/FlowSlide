"""
Authentication service for FlowSlide
"""

import logging
import secrets
import time
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..core.simple_config import app_config
from ..core.passwords import hash_password, verify_password
from ..database.models import User, UserSession

logger = logging.getLogger(__name__)


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
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise ValueError("用户名已存在")

        if email:
            existing_email = db.query(User).filter(User.email == email).first()
            if existing_email:
                raise ValueError("邮箱已存在")

        # Note: No external database check needed as per requirements
        # User synchronization is disabled

        # Create new user
        user = User(username=username, email=email, is_admin=is_admin)
        user.set_password(password)

        db.add(user)
        db.commit()
        db.refresh(user)

        # Note: No user sync triggered as per requirements

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

    def create_user_session(
        self, db: Session, user_or_id: int | User
    ) -> Optional[UserSession]:
        """Create a new session record for a user or user_id"""
        if isinstance(user_or_id, int):
            user = db.query(User).filter(User.id == user_or_id).first()
            if not user:
                return None
        else:
            user = user_or_id

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
        db.refresh(session)

        return session

    def create_session(self, db: Session, user: User) -> str:
        """Create a new session for user"""
        session = self.create_user_session(db, user)
        return session.session_id if session else ""

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

    def update_user_password(
        self, db: Session, user: User, new_password: str, current_password: Optional[str] = None
    ) -> bool:
        """Update the account attached to the writing session, not a detached snapshot."""
        try:
            account = (
                db.query(User)
                .filter(User.id == user.id, User.username == user.username, User.is_active.is_(True))
                .with_for_update()
                .first()
            )
            if account is None:
                return False
            if current_password is not None and not account.check_password(current_password):
                return False
            account.set_password(new_password)
            account.updated_at = time.time()
            # Existing cookies must not keep working after a credential change.
            db.query(UserSession).filter(UserSession.user_id == account.id).update(
                {"is_active": False}, synchronize_session=False
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            logger.exception("Password update failed")
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
            # Note: User sync disabled as per requirements
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
            account = db.query(User).filter(User.id == user.id, User.username == user.username).first()
            if account is None:
                raise ValueError("用户不存在")
            user = account
            if username and username != user.username:
                exists = db.query(User).filter(User.username == username).first()
                if exists:
                    raise ValueError("用户名已存在")
                user.username = username
                # Note: User sync disabled as per requirements
            if email is not None and email != user.email:
                if email:
                    exists = db.query(User).filter(User.email == email).first()
                    if exists:
                        raise ValueError("邮箱已存在")
                user.email = email
            user.updated_at = time.time()
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
            # Note: User sync disabled as per requirements
            return True
        except Exception:
            db.rollback()
            return False


# Global auth service instance
auth_service = AuthService()


def get_auth_service() -> AuthService:
    """Get auth service instance"""
    return auth_service


def init_default_admin(db: Session) -> bool:
    """Bootstrap only an empty authoritative database; never copy or reset accounts."""
    from sqlalchemy.exc import IntegrityError

    if db.query(User.id).first() is not None:
        return False
    try:
        auth_service.create_user(
            db=db,
            username=app_config.admin_username or 'admin',
            password=app_config.admin_password or 'admin123456',
            email=app_config.admin_email,
            is_admin=True,
        )
    except IntegrityError:
        # Another worker may have completed the bootstrap concurrently.
        db.rollback()
        if db.query(User.id).first() is not None:
            return False
        raise
    logger.info('Default administrator created in the authoritative database; change its password promptly')
    return True




