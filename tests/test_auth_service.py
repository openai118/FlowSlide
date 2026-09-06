import time
import pytest
from flowslide.auth.auth_service import AuthService, init_default_admin
from flowslide.core.simple_config import app_config
from flowslide.database.models import User, UserSession

def test_init_default_admin_empty_and_existing(test_session):
    # 1. Empty database: init_default_admin should create default admin
    created = init_default_admin(test_session)
    assert created is True
    expected_username = app_config.admin_username or "admin"
    expected_password = app_config.admin_password or "admin123456"
    admin = test_session.query(User).filter(User.username == expected_username).first()
    assert admin is not None
    assert admin.is_admin is True
    assert admin.check_password(expected_password)

    # 2. Database not empty: subsequent calls should return False and not alter accounts
    created_again = init_default_admin(test_session)
    assert created_again is False

def test_auth_service_create_and_authenticate(test_session):
    service = AuthService()
    user = service.create_user(
        test_session,
        username="john_doe",
        password="password123",
        email="john@example.com"
    )
    assert user.id is not None
    assert user.username == "john_doe"

    # Authenticate valid
    auth_user = service.authenticate_user(test_session, "john_doe", "password123")
    assert auth_user is not None
    assert auth_user.id == user.id

    # Authenticate invalid password
    assert service.authenticate_user(test_session, "john_doe", "wrong") is None
    # Authenticate unknown user
    assert service.authenticate_user(test_session, "nonexistent", "password123") is None

def test_update_user_password_and_invalidate_sessions(test_session):
    service = AuthService()
    user = service.create_user(
        test_session,
        username="alice",
        password="old_password_123",
        email="alice@example.com"
    )

    # Create active sessions for alice
    session1 = service.create_user_session(test_session, user.id)
    session2 = service.create_user_session(test_session, user.id)
    assert session1 is not None
    assert session2 is not None

    # Verify sessions are active
    active_sessions = test_session.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.is_active.is_(True)
    ).all()
    assert len(active_sessions) == 2

    # Wrong current password fails
    res_wrong = service.update_user_password(
        test_session, user, "new_password_456", current_password="wrong_current"
    )
    assert res_wrong is False

    # Correct current password succeeds
    res_ok = service.update_user_password(
        test_session, user, "new_password_456", current_password="old_password_123"
    )
    assert res_ok is True

    # Check password updated
    updated_user = service.get_user_by_id(test_session, user.id)
    assert updated_user.check_password("new_password_456")
    assert not updated_user.check_password("old_password_123")

    # Check sessions invalidated
    active_sessions_after = test_session.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.is_active.is_(True)
    ).all()
    assert len(active_sessions_after) == 0

    # Old session lookup should now fail
    assert service.get_user_by_session(test_session, session1.session_id) is None

def test_update_user_info_uniqueness(test_session):
    service = AuthService()
    u1 = service.create_user(test_session, "user1", "pass123", email="u1@test.com")
    u2 = service.create_user(test_session, "user2", "pass123", email="u2@test.com")

    # Update valid
    assert service.update_user_info(test_session, u1, username="user1_new", email="u1_new@test.com") is True

    # Colliding username
    with pytest.raises(ValueError, match="用户名已存在"):
        service.update_user_info(test_session, u2, username="user1_new")

    # Colliding email
    with pytest.raises(ValueError, match="邮箱已存在"):
        service.update_user_info(test_session, u2, email="u1_new@test.com")
