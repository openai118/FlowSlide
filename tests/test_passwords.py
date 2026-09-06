import pytest
import bcrypt
from flowslide.core.passwords import hash_password, verify_password, MAX_PASSWORD_BYTES

def test_hash_password_success():
    hashed = hash_password("mypassword123")
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")
    assert verify_password("mypassword123", hashed)
    assert not verify_password("wrongpassword", hashed)

def test_hash_password_empty_or_invalid():
    with pytest.raises(ValueError, match="密码不能为空"):
        hash_password("")
    with pytest.raises(ValueError, match="密码不能为空"):
        hash_password(None)

def test_hash_password_length_boundary():
    # Exactly 72 bytes in UTF-8 should succeed
    exact_72_bytes = "a" * 72
    hashed = hash_password(exact_72_bytes)
    assert verify_password(exact_72_bytes, hashed)

    # 73 bytes should raise ValueError
    over_72_bytes = "a" * 73
    with pytest.raises(ValueError, match="密码的 UTF-8 编码不能超过 72 字节"):
        hash_password(over_72_bytes)

    # Multi-byte UTF-8 boundary: 24 Chinese characters * 3 bytes = 72 bytes
    chinese_72 = "测" * 24
    assert len(chinese_72.encode("utf-8")) == 72
    h_cn = hash_password(chinese_72)
    assert verify_password(chinese_72, h_cn)

    # 25 Chinese characters * 3 bytes = 75 bytes
    chinese_over = "测" * 25
    with pytest.raises(ValueError, match="密码的 UTF-8 编码不能超过 72 字节"):
        hash_password(chinese_over)

def test_verify_password_invalid_hash_format():
    assert not verify_password("secret", "")
    assert not verify_password("secret", "not-a-bcrypt-hash")
    assert not verify_password("secret", None)
    assert not verify_password(None, "$2b$12$somehash")

def test_verify_legacy_hashes():
    # Test $2a$, $2b$, $2y$ prefixes
    raw = b"legacy_secret"
    salt = bcrypt.gensalt(prefix=b"2b", rounds=10)
    h_2b = bcrypt.hashpw(raw, salt).decode("ascii")
    assert verify_password("legacy_secret", h_2b)

    # Modify prefix to $2a$ and $2y$
    h_2a = "$2a$" + h_2b[4:]
    h_2y = "$2y$" + h_2b[4:]
    assert verify_password("legacy_secret", h_2a)
    assert verify_password("legacy_secret", h_2y)

def test_verify_legacy_long_password_truncation():
    # In legacy systems, long passwords were cut at 72 bytes
    long_pass = "x" * 100
    salt = bcrypt.gensalt(prefix=b"2b", rounds=10)
    # create hash using first 72 bytes
    h = bcrypt.hashpw(("x" * 72).encode("utf-8"), salt).decode("ascii")
    # verify_password should truncate and verify successfully for legacy compatibility
    assert verify_password(long_pass, h)
    assert not verify_password("x" * 71 + "y", h)
