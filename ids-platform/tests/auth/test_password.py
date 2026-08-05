"""Tests for password.py."""

from backend.auth.password import hash_password, verify_password


def test_hash_is_not_the_plain_password():
    hashed = hash_password("SuperSecret123!")
    assert hashed != "SuperSecret123!"


def test_verify_correct_password():
    hashed = hash_password("SuperSecret123!")
    assert verify_password("SuperSecret123!", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("SuperSecret123!")
    assert verify_password("WrongPassword", hashed) is False


def test_same_password_produces_different_hashes_each_time():
    # bcrypt salts each hash independently - two hashes of the same
    # password must never be identical (rules out a broken/no-op salt).
    hash1 = hash_password("SuperSecret123!")
    hash2 = hash_password("SuperSecret123!")
    assert hash1 != hash2
    assert verify_password("SuperSecret123!", hash1) is True
    assert verify_password("SuperSecret123!", hash2) is True


def test_verify_against_malformed_hash_fails_closed_not_open():
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False
