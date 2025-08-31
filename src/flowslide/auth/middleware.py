"""
Authentication middleware for FlowSlide
"""

import logging
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database.models import User
from .auth_service import get_auth_service

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """Authentication middleware"""

    def __init__(self):
        self.auth_service = get_auth_service()
        # 不需要认证的路径
        self.public_paths = {
            "/",
            "/home",
            "/scenarios",
            "/auth/login",
            "/auth/register",
            "/auth/logout",
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/check",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static",
            "/favicon.ico",
            "/health",
            "/api/health",
            "/api/database/health",
            "/api/database/health/quick",
            "/version.txt",
            "/api/version",
            "/api/global-master-templates",  # 临时允许模板API无需认证用于测试
            "/api/global-master-templates/",  # 带斜杠的版本
        }
        # 不需要认证的路径前缀
        self.public_prefixes = [
            "/static/",
            "/temp/",  # 添加temp目录用于图片缓存访问
            "/api/image/view/",  # 图床图片访问无需认证
            "/api/image/thumbnail/",  # 图片缩略图访问无需认证
            "/api/backup/",  # 备份API无需认证（用于自动化备份）
            "/api/system/",  # 系统监控API无需认证
            "/api/deployment/",  # 部署模式API无需认证
            "/api/config/",  # 配置API允许路由自行处理权限（GET 可公开返回掩码）
            "/api/global-master-templates/",  # 模板详情API无需认证
            "/home/",  # 允许 /home/ 形式
            "/scenarios/",  # 允许 /scenarios/ 形式
            "/docs",
            "/redoc",
            "/openapi.json",
            "/docs/",
            "/redoc/",
        ]

    def is_public_path(self, path: str) -> bool:
        """Check if path is public (doesn't require authentication)"""
        # Check exact matches
        if path in self.public_paths:
            return True

        # Check prefixes
        for prefix in self.public_prefixes:
            if path.startswith(prefix):
                return True

        return False

    async def __call__(self, request: Request, call_next: Callable):
        """Middleware function"""
        path = request.url.path

        # Always attempt to attach user to request if a valid session exists,
        # even for public paths, so templates can show correct login state.
        session_id = request.cookies.get("session_id")
        user = None
        if session_id:
            try:
                from ..database.database import SessionLocal
                db = SessionLocal()
                try:
                    user = self.auth_service.get_user_by_session(db, session_id)
                finally:
                    db.close()
            except Exception as e:
                logger.debug(f"Optional user attach failed: {e}")

        if user:
            request.state.user = user

        # Public paths don't require authentication; proceed immediately.
        is_public = self.is_public_path(path)
        if is_public:
            logger.debug(f"Public path allowed without auth: {path}")
            response = await call_next(request)
            return response
        else:
            logger.debug(f"Protected path requires auth: {path}")

        # For protected paths, enforce authentication
        if not user:
            # No valid session
            if path.startswith("/api/"):
                return Response(
                    content='{"detail": "Authentication required"}',
                    status_code=401,
                    media_type="application/json",
                )
            else:
                return RedirectResponse(url="/auth/login", status_code=302)

        # Authenticated, continue
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            if path.startswith("/api/"):
                return Response(
                    content='{"detail": "Authentication error"}',
                    status_code=500,
                    media_type="application/json",
                )
            else:
                return RedirectResponse(url="/auth/login", status_code=302)


def get_current_user(request: Request) -> Optional[User]:
    """Get current authenticated user from request"""
    return getattr(request.state, "user", None)


def require_auth(request: Request) -> User:
    """Dependency to require authentication"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(request: Request) -> User:
    """Dependency to require admin privileges"""
    user = require_auth(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


def get_current_user_optional(request: Request) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    # Create database session
    from ..database.database import SessionLocal
    if SessionLocal is None:
        return None
    db = SessionLocal()
    try:
        auth_service = get_auth_service()
        return auth_service.get_user_by_session(db, session_id)
    finally:
        db.close()


def get_current_user_required(request: Request) -> User:
    """Get current user, raise exception if not authenticated"""
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def get_current_admin_user(request: Request) -> User:
    """Get current admin user, raise exception if not admin"""
    user = get_current_user_required(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


def create_auth_middleware() -> AuthMiddleware:
    """Create authentication middleware instance"""
    return AuthMiddleware()


# Utility functions for templates
def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated"""
    return get_current_user(request) is not None


def is_admin(request: Request) -> bool:
    """Check if user is admin"""
    user = get_current_user(request)
    return user is not None and user.is_admin


def get_user_info(request: Request) -> Optional[dict]:
    """Get user info for templates"""
    user = get_current_user(request)
    if user:
        return user.to_dict()
    return None
