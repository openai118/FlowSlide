"""Password hashing shared by models, authentication and administrative tools."""

import re

import bcrypt

MAX_PASSWORD_BYTES = 72
_BCRYPT_HASH = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")


def hash_password(password: str) -> str:
    """Create a bcrypt hash without silently truncating a new password."""
    if not isinstance(password, str) or not password:
        raise ValueError("密码不能为空")
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError("密码的 UTF-8 编码不能超过 72 字节")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    """Verify existing bcrypt hashes, including legacy $2a$ / $2y$ hashes."""
    if not isinstance(password, str) or not isinstance(hashed, str):
        return False
    if not _BCRYPT_HASH.fullmatch(hashed):
        return False
    try:
        # Old bcrypt/Passlib installations accepted long passwords by using the
        # first 72 *bytes*. Preserve verification of those existing accounts;
        # hash_password() rejects overlong passwords for all new writes.
        encoded = password.encode("utf-8")[:MAX_PASSWORD_BYTES]
        return bcrypt.checkpw(encoded, hashed.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        return False
