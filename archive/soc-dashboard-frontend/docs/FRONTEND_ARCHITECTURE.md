# SOC Dashboard — Frontend Architecture (Milestone 7)

A React + TypeScript + Vite dashboard consuming the FastAPI backend built in
Milestones 4–6. This document covers architecture, component hierarchy,
routing, API integration, and WebSocket integration.

Screenshots of the running app (real backend, seeded demo data) are in
`docs/screenshots/`.

---

## 1. Folder Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── layout/       Sidebar, TopNav, Layout (shell every page renders inside)
│   │   ├── dashboard/    StatCard, SeverityBreakdownList, SystemHealthSummary
│   │   ├── alerts/       AlertsTable, AlertFiltersBar
│   │   ├── charts/       Recharts wrappers: threats-over-time, by-type, by-severity, top-IPs
│   │   ├── tables/       FlowsTable
│   │   ├── statistics/   LatencyGauge
│   │   └── common/       Badge, LoadingSkeleton, ErrorState, Pagination, SearchInput, StatusDot, NotAvailableCard
│   ├── pages/            Dashboard, Alerts, Flows, Statistics, SystemHealth, Settings
│   ├── hooks/             React Query hooks — one per backend domain
│   ├── services/          axios calls (one file per REST domain) + the WebSocket client class
│   ├── types/              TypeScript interfaces mirroring backend/api/schemas.py exactly
│   ├── context/            ThemeContext (dark mode), WebSocketContext (live alert feed)
│   ├── utils/               formatters.ts, severity.ts
│   └── App.tsx / main.tsx
├── docs/screenshots/       Real screenshots (see section 8)
├── .env.example
└── package.json
```

---

## 2. Component Hierarchy

```
App
├── QueryClientProvider           (React Query cache — see §5)
├── ThemeProvider                  (dark mode — UI state only, per spec)
├── BrowserRouter
│   └── WebSocketProvider          (owns the one AlertSocket connection — see §7)
│       └── Routes
│           └── Layout
│               ├── Sidebar        (nav links)
│               ├── TopNav         (StatusDot, dark-mode toggle)
│               └── <page>         (Outlet)
│                   ├── Dashboard    → StatCard×4, ThreatsByTypeChart, SeverityBreakdownList, SystemHealthSummary
│                   ├── Alerts       → AlertFiltersBar, AlertsTable, Pagination
│                   ├── Flows        → FlowsTable, Pagination
│                   ├── Statistics   → ThreatsOverTimeChart, ThreatsByTypeChart, ThreatsBySeverityChart,
│                   │                  TopSourceIPsChart, LatencyGauge, NotAvailableCard
│                   ├── SystemHealth → StatCard×4, NotAvailableCard×4, model info panel
│                   └── Settings     → theme toggle, connection info
```

Every page component only orchestrates hooks + presentational components — no
page makes an `axios` call directly; that's always through a `services/*.ts`
module via a `hooks/use*.ts` wrapper.

---

## 3. Routing

```
/                → Dashboard
/alerts          → Alerts (live table)
/flows           → Flows
/statistics       → Statistics
/system-health     → SystemHealth
/settings          → Settings
```

All routes render inside `<Layout>` (one `<Route element={<Layout />}>`
wrapping nested routes) via React Router's `<Outlet />`, so the
sidebar/top-nav never remount on navigation.

---

## 4. API Integration Guide

Every backend endpoint from Milestones 4–6 is wrapped by exactly one
`services/*.ts` function — **nothing was added to or changed in the
backend** for this milestone (per the spec's "reuse, don't modify" rule).

| Service | Backend endpoint(s) |
|---|---|
| `alertsService` | `GET /alerts`, `GET /alerts/{id}`, `GET /alerts/latest` |
| `flowsService` | `GET /flows` |
| `statisticsService` | `GET /statistics`, `GET /attacks/top` |
| `healthService` | `GET /health`, `GET /system/health` |
| `modelService` | `GET /model/info` |

Every `types/*.ts` interface field name matches its backend Pydantic schema
**exactly** — no renaming, no reshaping — so a payload straight off the
wire satisfies the TypeScript type with zero mapping code, and any future
backend field addition is a one-line type change, not a refactor.

**Base URL:** `VITE_API_BASE_URL` (`.env`, defaults to `http://localhost:8000`).

---

## 5. State Management

Per the spec's explicit rule — **React Query for API data, Context only for
UI state**:

- **React Query** (`@tanstack/react-query`) owns every server-fetched value:
  caching, retries (2, per `App.tsx`'s `QueryClient` config), loading/error
  states, and — critically — the cache that `WebSocketContext` writes
  directly into when a live alert arrives (see §7).
- **Context** is used for exactly two things, both pure UI state:
  `ThemeContext` (dark/light, persisted to `localStorage`) and
  `WebSocketContext` (connection status + the in-memory live-alert feed —
  itself sourced from a WebSocket, not a REST call, so it doesn't belong in
  React Query).

No Redux, no other global store — deliberately; this app's state needs don't
justify one.

---

## 6. Error Handling & Loading States

- **Loading:** every data-driven section shows a skeleton
  (`TableSkeleton` / `CardSkeleton` / `ChartSkeleton`) instead of a blank
  screen or spinner, so the layout doesn't jump when data arrives.
- **Errors:** `ErrorState` — a plain-language message plus a **Retry**
  button that calls React Query's `refetch()`. No raw error objects or
  stack traces are ever shown to the user.
- **Retry:** built into React Query itself (`retry: 2` globally) *and*
  manually available via the `ErrorState` button for a third, user-initiated
  attempt.
- **Pagination placeholder data:** `useAlerts`/`useFlows` use
  `placeholderData: (previous) => previous`, so changing a filter or page
  keeps the previous table visible (dimmed by React Query's `isPlaceholderData`
  if you want to style that — not currently styled differently, kept simple)
  instead of flashing to a skeleton on every keystroke.

---

## 7. WebSocket Integration Guide

```
Backend: DetectionService (worker thread)
  → AlertService.handle_detection()
    → broadcaster.publish_alert_threadsafe()
      → WS /ws/alerts
          │
          ▼
Frontend: AlertSocket (services/websocketService.ts)
  - raw `WebSocket`, exponential-backoff auto-reconnect (1s → 2s → 4s ... capped at 15s)
  - parses each message as `WSEvent`, notifies subscribers
          │
          ▼
WebSocketContext (context/WebSocketContext.tsx)
  1. Appends to `liveAlerts` (bounded to 200) — read via `useWebSocketAlerts()`
     for anything wanting the raw live feed (e.g. Dashboard's session
     "Active Alerts" count).
  2. `queryClient.setQueriesData(['alerts'], ...)` — prepends the new alert
     directly into the cached alerts-table query, so the Alerts page updates
     the instant a detection happens. No refetch, no polling.
  3. `queryClient.invalidateQueries(['statistics'])` — statistics are
     server-aggregated (counts, breakdowns), so rather than reimplementing
     that math client-side, this triggers exactly one refetch per alert.
     Still push-driven, not a polling interval.
```

**Live vs. persisted alert shape:** the WebSocket payload
(`backend/detection/alert.py`'s `Alert`) is missing `packet_count`, `bytes`,
and `status` compared to the REST `AlertResponse` (added later, at
persistence time, by `AlertService`) — `WebSocketContext` defaults
`status: "new"` when converting a live event into a table row, and simply
omits the two count fields, which the Alerts page's column set doesn't
require anyway. See `types/websocket.ts`'s docstring.

**The one intentional poll:** `useApiHealth`/`useSystemHealth` refetch every
30s — a heartbeat, not a data feed, and explicitly commented as such in
`hooks/useSystemHealth.ts`. Alerts, by contrast, never poll.

---

## 8. Honest Gaps (flagged, not faked)

Two spec'd displays have no backing data yet, and rather than inventing
numbers on a security dashboard, they say so plainly (`NotAvailableCard`):

- **System Health page:** CPU / Memory / Disk / Packet Rate — the backend
  has no OS-level telemetry endpoint (Milestone 6 never built one).
- **Statistics page:** "System Load" — same reason.

**Flows page "Prediction" column:** `FlowHistory` (backend) has no
`attack_type` column of its own — only `Alert` does, joined by `flow_id`.
The frontend does a best-effort client-side join against the latest 200
alerts (`pages/Flows.tsx`); flows outside that lookback window show `—`.

**Dashboard "Active Alerts":** the backend has no status-count endpoint, so
this is the count of `status === "new"` alerts in the current browser
session's live WebSocket feed — not a full historical count. Labeled
"(session)" in the UI to be unambiguous.

---

## 9. Design Decisions

- **Dark by default** — an operations-monitoring tool convention; toggle in
  Settings/TopNav persists to `localStorage`.
- **Monospace for data** (`JetBrains Mono`) — IDs, IPs, timestamps, counts —
  genuinely aids scanning tabular network data, paired with `Inter` for UI chrome.
- **The live pulse (`StatusDot`)** is the one signature visual element: a
  radar-style animated dot tied directly to the real WebSocket connection
  state (`connecting`/`open`/`closed`/`error`) — not decorative.
- **Severity colors** (`utils/severity.ts`) are a single source of truth
  shared by table badges and every chart, so a color can never mean two
  different things in two different places.

---

## 10. Testing Instructions

```bash
npm install
npm test              # vitest run — 17 tests across 4 files
npm run dev            # local dev server (needs the backend running — see below)
npm run build           # type-check (tsc -b) + production build
```

Test coverage (per the spec's four required areas):
- **Dashboard** (`pages/Dashboard.test.tsx`) — stat cards, threats-today
  derivation, system health rendering, accuracy formatting — services mocked
  with `vi.mock`.
- **Alert Table** (`components/alerts/AlertsTable.test.tsx`) — row
  rendering, empty state, sort-column click callback, sort-direction indicator.
- **Statistics** (`pages/Statistics.test.tsx`) — latency/accuracy figures,
  top-attacks list, and explicitly verifies the "System Load" honesty label
  (not a fabricated number).
- **WebSocket** (`services/websocketService.test.ts`) — connection status
  transitions, message parsing, malformed-message resilience, reconnect
  backoff, explicit-disconnect (no reconnect), listener unsubscription — all
  against a fake `WebSocket` (`vi.stubGlobal`), no real network needed.

**Running against the real backend** (for `npm run dev` or to reproduce the
screenshots):
```bash
# Terminal 1 - from the ids-platform project root
uvicorn backend.main:app --reload

# Terminal 2
cd frontend
cp .env.example .env   # defaults already point at localhost:8000
npm run dev
```

---

## 11. Screenshots

Captured from the actual running app (Vite production build, real FastAPI
backend, SQLite-backed, seeded with ~140 synthetic alerts) via Playwright —
not mockups.

| Page | File |
|---|---|
| Dashboard | `docs/screenshots/dashboard.png` |
| Live Alerts | `docs/screenshots/alerts.png` |
| Flows | `docs/screenshots/flows.png` |
| Statistics | `docs/screenshots/statistics.png` |
| System Health | `docs/screenshots/system-health.png` |

---

## 12. Milestone 8 Addendum: Response Engine Integration

Three new pages, following the exact same patterns established in
Milestone 7 (services → hooks → pages, React Query for server data):

- **Response Center** (`/response-center`) — manually trigger a response
  for any recent alert (with an optional action-list override), and watch
  the live response-activity feed.
- **Response History** (`/response-history`) — full paginated, filterable
  (`alert_id`, `action`, `status`, `mode`) history of every executed
  action, with a **Rollback** button wherever `rollback_available` is true.
- **Policy Manager** (`/policy-manager`) — toggle simulation/live mode and
  edit severity → action mappings by clicking action chips; validates and
  persists via `PUT /response-rules`.

**WebSocket:** `WebSocketContext` now also handles
`response_started`/`response_completed`/`response_failed`/`rollback_completed`
events on the same `/ws/alerts` connection (no second socket) — these
invalidate the `responses` and `alerts` query caches, so the Response
History table and any alert's `status` update instantly, live, with no
polling. Verified end-to-end against the running backend (screenshots
below were captured with the response engine live-wired and actually
executing).

**New types/services/hooks**: `types/response.ts`, `services/responsesService.ts`,
`hooks/useResponses.ts` (`useResponses`, `useResponseHistory`, `useResponseRules`,
`useExecuteResponse`, `useRollbackResponse`, `useUpdateResponseRules`) — same
one-file-per-domain convention as every other Milestone 7 service.

Screenshots: `docs/screenshots/{response-center,response-history,policy-manager}.png`.

---

## 13. Milestone 9 Addendum: Authentication

New: `src/auth/{Login,Register,ForgotPassword,ResetPassword,Profile,ProtectedRoute}.tsx`,
`src/context/AuthContext.tsx`, `src/services/authService.ts`, `src/utils/tokenStorage.ts`.

**Every protected route** (`App.tsx`) is wrapped in `<ProtectedRoute requiredPermission="...">`
matching exactly the permission its corresponding backend endpoint requires
(see `docs/AUTHENTICATION.md`'s permission matrix) — so a hidden sidebar
link and a 403-on-click can never disagree, because both read from the
same source (`AuthContext.hasPermission`, built from the same
`backend/auth/permissions.py` catalog).

`apiClient.ts` gained request/response interceptors: every request gets
`Authorization: Bearer <token>` attached automatically; any 401 triggers
one shared, de-duplicated silent refresh attempt before falling back to a
session-expired redirect. `WebSocketContext` now only connects once
authenticated, and tears down/reconnects as auth state changes.

Screenshot: `docs/screenshots/login-page.png` (the unauthenticated redirect,
captured live against the real backend). Full login→dashboard flow was
additionally verified via curl against the running server (401 → login →
200, documented in `docs/AUTHENTICATION.md` §5) and via the automated test
suite (`src/auth/*.test.tsx`) — live screenshots of the post-login state
hit repeated environment timeouts this round; the underlying flow is
proven working through the other two verification paths.

---

## 14. Milestone 10 Addendum: Reports, Analytics, Threat Intelligence, Incidents, Notifications

Five new pages, same established patterns: `Reports.tsx` (generate +
download PDF/CSV/JSON), `Analytics.tsx` (reuses Milestone 7's existing
chart components - `ThreatsOverTimeChart`, `ThreatsByTypeChart`,
`ThreatsBySeverityChart`, `TopSourceIPsChart` - directly, rather than
rebuilding equivalents, plus two new ones: `IncidentStatusChart`,
`ResponseTimeChart`), `ThreatIntelligence.tsx` (filterable indicator
table), `IncidentManager.tsx` (create incidents, inline status/owner
editing, expandable timeline + note-adding), `NotificationSettings.tsx`
(test-fire any severity's configured channels).

New types/services/hooks follow the exact one-file-per-domain convention
every prior milestone used: `types/{reports,analytics,threatIntel,incidents,notifications}.ts`,
matching `services/` and `hooks/` files.

**Honesty note on screenshots**: this round's live-screenshot capture hit
a real environment issue - the backend process died partway through the
Playwright script (each of Playwright's page navigations is a full
browser reload, which re-runs `AuthContext`'s session-restore-on-mount;
once the backend was gone, that legitimately failed and correctly
redirected to `/login`, which is exactly what should happen when a
session can't be verified - so the *code* behaved correctly, the
*infrastructure* just didn't stay up long enough to capture the
authenticated views). Verified instead via: (1) the full automated test
suite (412 tests: 387 backend + 25 frontend, including a new
`Analytics.test.tsx`), and (2) extensive `curl`/`TestClient`-based
end-to-end verification against the real running backend, documented in
`docs/PLATFORM_EXTENSIONS.md` §12 (threat-intel tagging and automated
response both firing correctly for the same alert, PDF/CSV/JSON export all
producing real output, incident CRUD and status transitions all verified
live).
