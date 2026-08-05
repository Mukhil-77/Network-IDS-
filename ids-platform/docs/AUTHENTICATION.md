# Authentication & Authorization (Milestone 9)

Secures the platform itself: JWT auth, refresh-token rotation, RBAC with
fine-grained permissions, session management, and audit logging — layered
onto every existing endpoint without duplicating any prior milestone's logic.

## 1. Authentication Architecture

```
┌──────────┐   POST /auth/login    ┌────────────────────┐
│  Client   │ ─────────────────────▶│ authentication.py   │
│           │                       │  authenticate_user() │──▶ password.py (bcrypt verify)
│           │◀───────────────────── │  issue tokens         │──▶ jwt_manager.py (encode)
│           │  access + refresh      │  create UserSession    │──▶ auth/models.py (DB)
└──────────┘                       └────────────────────────┘
     │
     │  every subsequent request: Authorization: Bearer <access_token>
     ▼
┌──────────────────┐     ┌───────────────────┐     ┌────────────────┐
│ dependencies.py    │────▶│ jwt_manager.py       │────▶│  route handler   │
│ get_current_user()  │     │ decode_token()         │     │  (200 or 403)     │
└──────────────────┘     └───────────────────┘     └────────────────┘
     │  401 if missing/invalid/expired token
     ▼
  Client (apiClient.ts's interceptor attempts one silent refresh, then
          redirects to /login if that also fails)
```

## 2. RBAC Permission Matrix

| Permission | Admin | Security Analyst | Viewer |
|---|:---:|:---:|:---:|
| alerts:read | ✅ | ✅ | ✅ |
| alerts:write | ✅ | ✅ | ❌ |
| flows:read | ✅ | ✅ | ✅ |
| statistics:read | ✅ | ✅ | ✅ |
| predict:execute | ✅ | ✅ | ❌ |
| responses:read | ✅ | ✅ | ❌ |
| responses:execute | ✅ | ✅ | ❌ |
| settings:read | ✅ | ✅ | ❌ |
| settings:write | ✅ | ❌ | ❌ |
| users:read | ✅ | ❌ | ❌ |
| users:write | ✅ | ❌ | ❌ |
| roles:read | ✅ | ❌ | ❌ |
| audit:read | ✅ | ✅ | ❌ |

Defined in `backend/auth/permissions.py`, seeded into the database once at
first startup (`seed_default_data()` — idempotent, never overwrites data an
operator has since changed). Permissions are real DB rows
(many-to-many `Role ↔ Permission`), not a hardcoded `if role == "Admin"` —
reassigning what a role can do is a data change, not a code change.

## 3. Database Schema

```
┌──────────┐  role_id  ┌──────────┐  role_permissions  ┌──────────────┐
│  User      │─────────▶│  Role      │◀───────────────────▶│  Permission    │
│  id (PK)    │           │  id (PK)    │   (many-to-many)     │  id (PK)        │
│  username    │           │  name        │                       │  name            │
│  email        │           │  description  │                       │  description      │
│  hashed_pw     │           └──────────┘                       └──────────────┘
│  is_active      │
│  last_login_at   │
└──────────┘
     │  user_id
     ▼
┌────────────────┐
│  UserSession      │   one row per issued refresh token - see §4
│  id = jti (PK)      │
│  refresh_token_hash  │
│  expires_at            │
│  revoked                │
└────────────────┘

AuditLog (extended, not duplicated - see below)
│  user_id (FK, nullable), role, ip_address, status   ← added this milestone
│  actor, action, target, details, timestamp           ← existed since Milestone 6
```

**`AuditLog` was extended, not duplicated.** It already existed (Milestone
6, reused by Milestone 8's response engine) — this milestone added four
nullable columns (`user_id`, `role`, `ip_address`, `status`) rather than
creating a second audit table, so login/logout/response-execution/model-load
events all live in one queryable trail.

## 4. JWT Lifecycle

- **Access token** — 15 min default, stateless (never stored server-side —
  can't be revoked before expiry, which is exactly why it's short-lived).
- **Refresh token** — 7 days default. Its **hash** (SHA-256, not bcrypt —
  see `authentication.py`'s `_hash_token` docstring for why) is stored in
  `UserSession`, keyed by the token's `jti` claim.
- **Rotation**: every `POST /auth/refresh` call issues a brand-new
  access+refresh pair and immediately marks the old session `revoked=True`.
  A stolen refresh token that gets used once by an attacker becomes
  provably invalid the next time the legitimate owner tries to use it —
  detectable reuse, not silent compromise.
- **Logout**: `POST /auth/logout` marks the session `revoked=True`
  directly — no waiting for expiry.

## 5. API Security

Every route from Milestones 4–8 that isn't a health check now requires
authentication, via one of three dependencies
(`backend/auth/dependencies.py`): `get_current_user` (any valid token),
`require_permission("x:y")`, or `require_role(...)`. `GET /health` (root
liveness) stays public deliberately — infra monitoring tools querying it
don't hold API credentials.

`POST /responses/execute` and `/rollback` now use the **authenticated
user's real username** as the operator (not a client-supplied string) —
audit entries can no longer be spoofed to attribute an action to someone
else.

`WS /ws/alerts` requires `?token=<access_token>` (browsers can't set
custom headers during a WebSocket handshake) — an invalid/missing token
closes the connection with code 4401 before it's ever added to the
broadcast pool.

## 6. Frontend Authentication Flow

`AuthContext` (`src/context/AuthContext.tsx`) holds the current user and
exposes `login`/`register`/`logout`/`hasPermission`. `ProtectedRoute`
(`src/auth/ProtectedRoute.tsx`) redirects to `/login` (preserving the
attempted URL) if unauthenticated, or shows an inline "access denied" if
authenticated but lacking the route's required permission.
`apiClient.ts`'s response interceptor attempts one silent token refresh on
any 401, sharing a single in-flight refresh across simultaneous requests
(avoiding the rotation-reuse-detection false-positive that racing multiple
refresh calls would trigger); if that also fails, it dispatches
`SESSION_EXPIRED_EVENT`, which `AuthContext` turns into a dismissible
banner + redirect. `Sidebar.tsx` filters its nav items by
`hasPermission()`, so a Viewer never sees a "Policy Manager" link they'd
just get a 403 clicking.

## 7. Security Best Practices Implemented

- **Password hashing**: bcrypt, cost factor 12, salted per-password (see
  `auth/password.py`).
- **No username enumeration**: login and password-reset both return
  identical responses whether or not the account exists.
- **Fail closed**: a malformed stored password hash fails verification
  rather than raising past the check.
- **CORS**: configured (Milestone 4), unchanged.
- **Secure headers**: `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Strict-Transport-Security`, `Permissions-Policy` —
  new `SecurityHeadersMiddleware`, added to every response.
- **Rate limiting placeholder**: already existed (Milestone 4) - no new
  work needed here, reused as-is.
- **Input validation**: registration password requires 8+ chars, one
  uppercase, one digit (Pydantic validator); all request bodies are
  Pydantic-validated as everywhere else in this codebase.

**Known tradeoff, documented rather than hidden**: tokens are stored in
`localStorage` (`src/utils/tokenStorage.ts`), which is readable by any
script running on the page (XSS-exposed) — the standard alternative
(httpOnly cookies + a backend-for-frontend) requires infrastructure this
project doesn't have yet. Isolated to one file specifically so swapping the
strategy later doesn't ripple through the codebase.

## 8. Two Real Bugs Found and Fixed

1. **`get_db()` never committed.** Every write-capable route before this
   milestone used `session_scope()` (which explicitly commits) rather than
   the FastAPI `Depends(get_db)` dependency directly. Milestone 9's auth
   routes are the first to mutate data via `Depends(get_db)` — which
   exposed that dependency silently rolling back every change when the
   session closed at the end of a request. Fixed to commit-on-success,
   mirroring `session_scope()`'s contract. (The test suite's own
   `get_db` override had the identical bug, independently, and needed the
   identical fix.)
2. **`Base.metadata.create_all()` didn't know about the auth tables** until
   something imported `backend.auth.models` — a classic SQLAlchemy
   declarative-registration gotcha. Fixed by importing that module inside
   `init_db()` itself.

## 9. Testing

```bash
python -m pytest tests/auth/ tests/api/test_auth_routes.py -v
```

56 new tests: password hashing/verification, JWT encode/decode/expiry/
tampering, the full authentication flow (login, refresh rotation, reuse
rejection, logout revocation), authorization/permission checks per role,
audit log writes, and — at the API layer — 401 enforcement on every newly-
protected endpoint, 403 enforcement per role (a Viewer genuinely cannot
execute a response; a Security Analyst genuinely cannot write settings),
and the full login→refresh→logout HTTP cycle.

**All 242 pre-Milestone-9 tests still pass unmodified** — the `client`/
`client_with_model` fixtures now auto-authenticate as the seeded default
Admin (who has every permission), so no earlier test needed to be rewritten
to add a token.

## 10. Default Credentials (change immediately)

A fresh deployment seeds one Admin account: username `admin`, password
from `DEFAULT_ADMIN_PASSWORD` (default `ChangeMe123!`) — logged loudly as
a warning on every startup that uses it. Change this password via
`PUT /auth/profile` (or the Profile page) immediately in any real
deployment.
