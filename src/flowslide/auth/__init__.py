"""
Authentication module for FlowSlide
"""

from .auth_service import AuthService, get_auth_service, init_default_admin
from .middleware import (
    AuthMiddleware,
    create_auth_middleware,
    get_current_admin_user,
    get_current_user,
    get_current_user_optional,
    get_current_user_required,
    get_user_info,
    is_admin,
    is_authenticated,
    require_admin,
    require_auth,
)
from .routes import router as auth_router

__all__ = [
    "AuthService",
    "get_auth_service",
    "init_default_admin",
    "AuthMiddleware",
    "create_auth_middleware",
    "get_current_user",
    "require_auth",
    "require_admin",
    "get_current_user_optional",
    "get_current_user_required",
    "get_current_admin_user",
    "is_authenticated",
    "is_admin",
    "get_user_info",
    "auth_router",
]
