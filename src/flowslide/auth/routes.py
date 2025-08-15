"""
Authentication routes for FlowSlide
"""

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import User
from .auth_service import AuthService, get_auth_service
from ..core.simple_config import app_config
from .middleware import (
    get_current_user_optional,
    get_current_user_required,
    get_current_admin_user,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Templates directory - use absolute path for better reliability  
import os
template_dir = os.path.join(os.path.dirname(__file__), "..", "web", "templates")
templates = Jinja2Templates(directory=template_dir)


@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(
    request: Request, error: str = None, success: str = None, username: str = None
):
    """Login page"""
    # Check if user is already logged in
    user = get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/home", status_code=302)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error,
            "success": success,
            "username": username,
            "turnstile_site_key": app_config.turnstile_site_key,
            "hcaptcha_site_key": app_config.hcaptcha_site_key,
            "enable_captcha": app_config.enable_login_captcha,
        },
    )


@router.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None, success: str = None):
    """Register page"""
    user = get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/home", status_code=302)

    return templates.TemplateResponse(
        "register.html",
        {"request": request, "error": error, "success": success},
    )


@router.post("/auth/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    cf_turnstile_response: str = Form(None, alias="cf-turnstile-response"),
    hcaptcha_response: str = Form(None, alias="h-captcha-response"),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Handle login form submission"""
    try:
        # Optional CAPTCHA verification
        if app_config.enable_login_captcha:
            verified = False
            # Prefer Cloudflare Turnstile if configured
            if app_config.turnstile_secret_key and cf_turnstile_response:
                try:
                    import httpx
                    resp = httpx.post(
                        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                        data={
                            "secret": app_config.turnstile_secret_key,
                            "response": cf_turnstile_response,
                            "remoteip": request.client.host if request.client else None,
                        },
                        timeout=5.0,
                    )
                    if resp.status_code == 200 and resp.json().get("success"):
                        verified = True
                except Exception:
                    verified = False
            # Fallback to hCaptcha
            if not verified and app_config.hcaptcha_secret_key and hcaptcha_response:
                try:
                    import httpx
                    resp = httpx.post(
                        "https://hcaptcha.com/siteverify",
                        data={
                            "secret": app_config.hcaptcha_secret_key,
                            "response": hcaptcha_response,
                            "remoteip": request.client.host if request.client else None,
                        },
                        timeout=5.0,
                    )
                    if resp.status_code == 200 and resp.json().get("success"):
                        verified = True
                except Exception:
                    verified = False

            if not verified:
                return templates.TemplateResponse(
                    "login.html",
                    {
                        "request": request,
                        "error": "人机验证失败，请重试",
                        "username": username,
                        "turnstile_site_key": app_config.turnstile_site_key,
                        "hcaptcha_site_key": app_config.hcaptcha_site_key,
                        "enable_captcha": app_config.enable_login_captcha,
                    },
                )
        # Authenticate user
        user = auth_service.authenticate_user(db, username, password)

        if not user:
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "error": "用户名或密码错误",
                    "username": username,
                    "turnstile_site_key": app_config.turnstile_site_key,
                    "hcaptcha_site_key": app_config.hcaptcha_site_key,
                    "enable_captcha": app_config.enable_login_captcha,
                },
            )

        # Create session
        session_id = auth_service.create_session(db, user)

    # Redirect to home
    response = RedirectResponse(url="/home", status_code=302)

        # Set cookie max_age based on session expiration
        # If session_expire_minutes is 0, set cookie to never expire (None means session cookie)
        current_expire_minutes = auth_service._get_current_expire_minutes()
        cookie_max_age = (
            None if current_expire_minutes == 0 else current_expire_minutes * 60
        )

        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=cookie_max_age,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
        )

        logger.info(f"User {username} logged in successfully")
        return response

    except Exception as e:
        logger.error(f"Login error: {e}")
    return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "登录过程中发生错误，请重试",
        "username": username,
        "turnstile_site_key": app_config.turnstile_site_key,
        "hcaptcha_site_key": app_config.hcaptcha_site_key,
        "enable_captcha": app_config.enable_login_captcha,
            },
        )


@router.post("/auth/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    email: str = Form(None),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Handle registration form submission"""
    try:
        if password != confirm_password:
            return templates.TemplateResponse(
                "register.html",
                {
                    "request": request,
                    "error": "两次输入的密码不一致",
                    "username": username,
                    "email": email,
                },
            )

        if len(password) < 6:
            return templates.TemplateResponse(
                "register.html",
                {
                    "request": request,
                    "error": "密码长度至少6位",
                    "username": username,
                    "email": email,
                },
            )

        # Create user
        auth_service.create_user(db, username=username, password=password, email=email)

        # Auto-login after registration
        user = auth_service.authenticate_user(db, username, password)
        session_id = auth_service.create_session(db, user)

    response = RedirectResponse(url="/home", status_code=302)

        current_expire_minutes = auth_service._get_current_expire_minutes()
        cookie_max_age = None if current_expire_minutes == 0 else current_expire_minutes * 60
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=cookie_max_age,
            httponly=True,
            secure=False,
            samesite="lax",
        )
        return response

    except ValueError as ve:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": str(ve),
                "username": username,
                "email": email,
            },
        )
    except Exception:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "注册失败，请稍后再试",
                "username": username,
                "email": email,
            },
        )


@router.get("/auth/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Logout user"""
    session_id = request.cookies.get("session_id")

    if session_id:
        auth_service.logout_user(db, session_id)

    response = RedirectResponse(
        url="/auth/login?success=已成功退出登录", status_code=302
    )
    response.delete_cookie("session_id")

    return response


@router.get("/auth/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request, user: User = Depends(get_current_user_required)
):
    """User profile page"""
    return templates.TemplateResponse(
        "profile.html", {"request": request, "user": user.to_dict()}
    )


@router.post("/auth/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Change user password"""
    try:
        # Validate current password
        if not user.check_password(current_password):
            return templates.TemplateResponse(
                "profile.html",
                {"request": request, "user": user.to_dict(), "error": "当前密码错误"},
            )

        # Validate new password
        if new_password != confirm_password:
            return templates.TemplateResponse(
                "profile.html",
                {
                    "request": request,
                    "user": user.to_dict(),
                    "error": "新密码和确认密码不匹配",
                },
            )

        if len(new_password) < 6:
            return templates.TemplateResponse(
                "profile.html",
                {
                    "request": request,
                    "user": user.to_dict(),
                    "error": "密码长度至少6位",
                },
            )

        # Update password
        if auth_service.update_user_password(db, user, new_password):
            return templates.TemplateResponse(
                "profile.html",
                {"request": request, "user": user.to_dict(), "success": "密码修改成功"},
            )
        else:
            return templates.TemplateResponse(
                "profile.html",
                {
                    "request": request,
                    "user": user.to_dict(),
                    "error": "密码修改失败，请重试",
                },
            )

    except Exception as e:
        logger.error(f"Change password error: {e}")
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user.to_dict(),
                "error": "修改密码过程中发生错误",
            },
        )


# API endpoints for authentication
@router.post("/api/auth/login")
async def api_login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    """API login endpoint"""
    user = auth_service.authenticate_user(db, username, password)

    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    session_id = auth_service.create_session(db, user)

    return {"success": True, "session_id": session_id, "user": user.to_dict()}


@router.post("/api/auth/logout")
async def api_logout(
    request: Request,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    """API logout endpoint"""
    session_id = request.cookies.get("session_id")

    if session_id:
        auth_service.logout_user(db, session_id)

    return {"success": True, "message": "已成功退出登录"}


@router.get("/api/auth/me")
async def api_current_user(user: User = Depends(get_current_user_required)):
    """Get current user info"""
    return {"success": True, "user": user.to_dict()}


# Admin and user management API
@router.get("/api/admin/users")
async def api_list_users(
    request: Request, admin: User = Depends(get_current_admin_user), db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return {"success": True, "users": [u.to_dict() for u in users]}


@router.post("/api/admin/users")
async def api_create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(None),
    is_admin: bool = Form(False),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        user = auth_service.create_user(db, username=username, password=password, email=email, is_admin=is_admin)
        return {"success": True, "user": user.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/admin/users/{user_id}")
async def api_delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    ok = auth_service.delete_user_by_id(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True}


@router.post("/api/auth/profile/update")
async def api_update_profile(
    request: Request,
    username: str = Form(None),
    email: str = Form(None),
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        auth_service.update_user_info(db, user, username=username, email=email)
        return {"success": True, "user": user.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/auth/check")
async def api_check_auth(request: Request, db: Session = Depends(get_db)):
    """Check authentication status"""
    user = get_current_user_optional(request, db)

    return {"authenticated": user is not None, "user": user.to_dict() if user else None}
