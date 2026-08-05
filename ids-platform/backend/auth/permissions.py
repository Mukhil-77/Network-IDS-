"""
The permission catalog and default role -> permission mappings.

This is the "future-ready fine-grained permission model" from the spec:
permissions are real DB rows (auth/models.py's Permission,
many-to-many with Role via role_permissions), not a hardcoded enum baked
into `if` statements - adding a permission or reassigning which roles have
it is a data change (via seed_default_data() below, or directly through
the database), not a code change. What lives in code is only the
*default* catalog and the *default* role assignments, seeded once at
first startup (see authentication.py's seed_default_data()) - after that,
the database is the source of truth.
"""

from __future__ import annotations

# name -> human-readable description. `resource:action` naming keeps the
# catalog scannable and makes wildcarding-by-resource straightforward if
# that's ever needed.
PERMISSION_CATALOG: dict[str, str] = {
    "alerts:read": "View alerts",
    "alerts:write": "Acknowledge / update alert status",
    "flows:read": "View network flows",
    "statistics:read": "View statistics and reports",
    "predict:execute": "Submit a prediction request",
    "responses:read": "View response history",
    "responses:execute": "Trigger or roll back a response action",
    "settings:read": "View response policy configuration",
    "settings:write": "Modify response policy configuration",
    "users:read": "View user accounts",
    "users:write": "Create or modify user accounts",
    "roles:read": "View roles and their permissions",
    "audit:read": "View the audit log",
    # Milestone 10
    "reports:read": "View generated reports",
    "reports:generate": "Generate a new report",
    "analytics:read": "View analytics and trends",
    "threat_intel:read": "View threat intelligence indicators",
    "incidents:read": "View incidents",
    "incidents:write": "Create, assign, or update incidents",
    "notifications:test": "Send a test notification",
}

# Default role -> permission-name set. Applied only when seeding a fresh
# database (existing roles/permissions are never overwritten by this - see
# seed_default_data()), so an operator's later changes via PUT-style role
# management always win over these defaults on subsequent restarts.
DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "Admin": set(PERMISSION_CATALOG.keys()),  # full access
    "Security Analyst": {
        "alerts:read", "alerts:write", "flows:read", "statistics:read",
        "predict:execute", "responses:read", "responses:execute",
        "settings:read", "audit:read",
        # Milestone 10: an analyst manages incidents, reads reports/analytics/threat intel, and can test notification channels
        "reports:read", "reports:generate", "analytics:read", "threat_intel:read",
        "incidents:read", "incidents:write", "notifications:test",
    },
    "Viewer": {
        "alerts:read", "flows:read", "statistics:read",
        # Milestone 10: read-only extends naturally to these too
        "reports:read", "analytics:read", "threat_intel:read", "incidents:read",
    },
}

DEFAULT_ROLE_DESCRIPTIONS: dict[str, str] = {
    "Admin": "Full platform access, including user and policy management.",
    "Security Analyst": "Can view alerts, execute responses, and view reports.",
    "Viewer": "Read-only dashboard access.",
}
