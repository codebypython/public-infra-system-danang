"""Unit tests for security primitives — pure functions, no DB."""

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("Secret@123")
    assert verify_password("Secret@123", h)
    assert not verify_password("wrong", h)


def test_access_token_roundtrip():
    t = create_access_token("00000000-0000-0000-0000-000000000001", role="admin")
    p = decode_token(t)
    assert p["role"] == "admin"
    assert p["type"] == "access"
    assert "jti" in p


def test_refresh_token_distinct():
    t1, _ = create_refresh_token("user-1")
    t2, _ = create_refresh_token("user-1")
    assert t1 != t2  # jti differs
