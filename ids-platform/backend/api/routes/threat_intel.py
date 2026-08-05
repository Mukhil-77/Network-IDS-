"""
Threat intelligence endpoints (documented path: api/routes/threat_intel.py).

The implementation lives in backend/api/routes/threat_intelligence.py
(GET /threat-intelligence - lists known threat indicators, filterable by
tag). This module is the documented entry point and re-exports the router so
both module names resolve identically; api_router includes the router via
the threat_intelligence module, so endpoints are registered exactly once.
"""

from backend.api.routes.threat_intelligence import router

__all__ = ["router"]
