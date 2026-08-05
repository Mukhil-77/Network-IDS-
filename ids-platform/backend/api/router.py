"""
Central router aggregation (the documented api/router.py entry point).

The full router - auth included - is assembled here and exported as
``router``. It is nothing but a re-export of the aggregation that already
lives in backend/api/routes/__init__.py (``api_router``) plus the auth
router, which main.py has always mounted separately at the root level.

Using this module is equivalent to what main.py does today:

    app.include_router(router)          # everything, auth included

It exists so the documented folder structure (api/router.py) is a real,
importable module instead of an empty placeholder, without duplicating the
aggregation list in two places that could drift apart.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.routes import api_router as routes_aggregation
from backend.auth.routes import router as auth_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(routes_aggregation)

__all__ = ["router"]
