"""
Authentication & user management routes (documented path: api/routes/auth.py).

The real implementation lives in backend/auth/routes.py, and main.py mounts
it at the application root (``app.include_router(auth_router)``) so the
endpoints are served under /auth/... and /users..., /roles..., /audit...
without a duplicated prefix.

This module re-exports that router so ``from backend.api.routes.auth import
router`` works exactly like the documented structure promises. It is *not*
included in api_router (see backend/api/router.py) - doing so would register
every auth endpoint a second time and FastAPI would reject the duplicates.

Endpoints (all defined in backend/auth/routes.py):
    POST   /auth/login, /auth/refresh, /auth/logout, /auth/register
    GET    /auth/me, /users, /roles, /audit
    PUT    /auth/profile
    POST   /auth/forgot-password, /auth/reset-password
"""

from backend.auth.routes import router

__all__ = ["router"]
