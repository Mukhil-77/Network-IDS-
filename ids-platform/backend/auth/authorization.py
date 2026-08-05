"""
Permission checking against a loaded User (with its Role -> Permissions
relationship). No DB access here - dependencies.py is what loads the user;
this module is pure logic, which is what makes it directly unit-testable.
"""

from __future__ import annotations

from backend.auth.models import User


def user_permissions(user: User) -> set[str]:
    return {p.name for p in user.role.permissions}


def has_permission(user: User, permission: str) -> bool:
    return permission in user_permissions(user)


def has_any_permission(user: User, *permissions: str) -> bool:
    granted = user_permissions(user)
    return any(p in granted for p in permissions)


def has_role(user: User, *role_names: str) -> bool:
    return user.role.name in role_names
