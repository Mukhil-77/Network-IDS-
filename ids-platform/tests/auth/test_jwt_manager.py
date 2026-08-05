"""Tests for jwt_manager.py."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.auth.jwt_manager import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    ExpiredTokenError,
    InvalidTokenError,
    _encode,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_access_token_round_trips():
    token = create_access_token("user-1", "alice", "Admin")
    payload = decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
    assert payload.sub == "user-1"
    assert payload.username == "alice"
    assert payload.role == "Admin"
    assert payload.type == ACCESS_TOKEN_TYPE


def test_refresh_token_round_trips_and_returns_jti_and_expiry():
    token, jti, expires_at = create_refresh_token("user-1", "alice", "Admin")
    payload = decode_token(token, expected_type=REFRESH_TOKEN_TYPE)
    assert payload.jti == jti
    assert payload.type == REFRESH_TOKEN_TYPE
    assert expires_at > datetime.now(timezone.utc)


def test_decode_rejects_wrong_expected_type():
    access = create_access_token("user-1", "alice", "Admin")
    with pytest.raises(InvalidTokenError, match="Expected a 'refresh' token"):
        decode_token(access, expected_type=REFRESH_TOKEN_TYPE)


def test_decode_rejects_tampered_signature():
    token = create_access_token("user-1", "alice", "Admin")
    tampered = token[:-4] + "abcd"
    with pytest.raises(InvalidTokenError):
        decode_token(tampered)


def test_decode_rejects_malformed_token():
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-jwt-at-all")


def test_decode_raises_expired_token_error_for_an_expired_token():
    token, _ = _encode("user-1", "alice", "Admin", ACCESS_TOKEN_TYPE, timedelta(seconds=-1))
    with pytest.raises(ExpiredTokenError):
        decode_token(token)


def test_each_token_gets_a_unique_jti():
    _, jti1, _ = create_refresh_token("user-1", "alice", "Admin")
    _, jti2, _ = create_refresh_token("user-1", "alice", "Admin")
    assert jti1 != jti2
