"""
Password hashing via bcrypt directly (not passlib - passlib's bcrypt
backend has had version-detection issues with recent bcrypt releases; the
`bcrypt` package's own API is small enough not to need a wrapper).

bcrypt has a hard 72-byte input limit - passwords are truncated to that
length by the library, not silently mishandled; UTF-8 encoding happens
before hashing so multi-byte characters count correctly.
"""

from __future__ import annotations

import bcrypt

_BCRYPT_ROUNDS = 12  # cost factor - 12 is a reasonable balance of security vs. login latency in 2026


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed stored hash (shouldn't happen outside a corrupted DB row) - fail closed, not open.
        return False
