# Reporting, Threat Intelligence, Notifications, Analytics, Incident Management (Milestone 10)

Transforms the platform into a professional SOC: on-demand reports,
a modular threat intelligence framework, configurable notification
routing, an analytics/trends engine, and full incident lifecycle
management — all composed from existing services, nothing duplicated.

## 1. Updated Folder Structure

```
backend/
├── reports/            {report_service, pdf_generator, csv_export}.py + templates/report_templates.py
├── notifications/       {email_service, telegram_service, webhook_service, notification_manager}.py + config/notification_rules.yaml
├── threat_intelligence/  {indicators, reputation, feeds, enrichment}.py + data/demo_feed.json
├── analytics/             {analytics_service, trends, forecasting}.py
├── database/repositories/incidents.py    (new)
├── services/incident_service.py            (new - lifecycle/state machine)
└── api/routes/{reports,analytics,threat_intelligence,incidents,notifications}.py
```

## 2. Architecture Diagram

```
Alert persisted (AlertService, Milestone 6)
    │
    ▼
main.py's composite on_alert_persisted callback
    ├──▶ threat_intelligence.enrichment.enrich_and_tag()
    │        └──▶ reputation.ReputationRegistry (cached, provider-chain lookup)
    │                 └──▶ StaticIndicatorProvider  (checks ThreatIndicator table)
    │        writes Alert.threat_tag
    │
    └──▶ response_engine.response_service.handle_alert()   (Milestone 8, unchanged)
             └──▶ send_email/send_telegram/webhook_notification actions
                      now delegate to notifications/{email,telegram,webhook}_service.py
                      (moved here from response_engine/notifications.py - no more duplicate SMTP/HTTP code)

Analyst-triggered, on demand:
    GET /reports, POST /reports/generate  ──▶ report_service (composes analytics_service +
                                                repositories) ──▶ pdf_generator / csv_export / json
    GET /analytics, /analytics/trends      ──▶ analytics_service (composes statistics_service,
                                                Milestone 6, + trends.py + forecasting.py)
    GET /threat-intelligence                ──▶ ThreatIndicator table directly
    POST /notifications/test                 ──▶ notification_manager (severity -> channels,
                                                configurable, same YAML-rules pattern as
                                                response_rules.py)
    /incidents (GET/POST/PUT)                 ──▶ incident_service (state machine + timeline)
```

## 3. Threat Intelligence Workflow

Every persisted alert's source IP is checked against a chain of
`ReputationProvider`s (`reputation.py`) - first non-`None` result wins, with
a 5-minute TTL cache in front so a burst of alerts from the same IP doesn't
re-query for each one. The built-in `StaticIndicatorProvider` checks the
`ThreatIndicator` table (seeded at every startup from a bundled demo feed -
see `feeds.py`'s docstring for exactly why this is illustrative data, not a
real feed, and how a real one - AbuseIPDB, AlienVault OTX - plugs into the
identical interface). No opinion from any provider → `ThreatTag.UNKNOWN`,
never a crash. A provider that raises (simulating a real feed's network
outage) is caught and skipped, falling through to the next one.

## 4. Reporting Workflow

`report_service.generate(db, report_type, ...)` looks up which sections a
report type includes (`templates/report_templates.py` - a declarative
mapping, not Jinja/HTML templates, since `pdf_generator.py` builds PDFs
programmatically with reportlab rather than rendering HTML), builds each
section by calling existing services (`analytics_service.get_overview()`,
`AttackStatisticsRepository.top()`, `IncidentRepository.list()`, ...), and
returns one plain dict. `pdf_generator.py`/`csv_export.py`/`json.dumps`
each turn that same dict into their format - the data is computed exactly
once regardless of which export format was requested.

## 5. Notification Workflow

`NotificationManager` (`notification_manager.py`) is a second,
independent YAML-configured rules engine alongside `response_rules.py`'s
`PolicyEngine` — deliberately not merged with it. `response_rules.yaml`
answers "what actions (including possibly `send_email`) should run for
this severity as part of the response policy"; `notification_rules.yaml`
answers "which notification channels should this severity reach" as a
standalone concept. **Only one of these actually fires automatically per
alert today** (the response policy, via `main.py`'s wiring, unchanged from
Milestone 8) — `NotificationManager` is currently wired to `POST
/notifications/test` only, so an operator can verify a channel's
configuration without waiting for a real alert or accidentally double-
sending. Wiring `NotificationManager` to also fire automatically (in
addition to or instead of the response policy's notify actions) is a
one-line addition to `main.py`'s composite callback whenever that's
wanted — deliberately not done in this milestone to avoid Critical alerts
silently emailing twice.

## 6. API Documentation

| Endpoint | Permission | Notes |
|---|---|---|
| `GET /reports` | `reports:read` | Lists available report *types* (generated on demand, not a stored library) |
| `POST /reports/generate` | `reports:generate` | Returns a file download (`json`/`csv`/`pdf`) |
| `GET /analytics` | `analytics:read` | Full overview - see example below |
| `GET /analytics/trends` | `analytics:read` | Timeline + forecast |
| `GET /threat-intelligence` | `threat_intel:read` | Filterable by `tag` |
| `GET /incidents` | `incidents:read` | Paginated, filterable by `status`/`severity`/`owner` |
| `POST /incidents` | `incidents:write` | Opens an incident |
| `PUT /incidents/{id}` | `incidents:write` | Status/owner/priority/note - validates transitions |
| `POST /notifications/test` | `notifications:test` | Fires the configured channels for one severity |

## 7. Database Updates

- **`Alert.threat_tag`** (additive column) - set by enrichment.
- **`ThreatIndicator`** (new table) - Known Malicious IP List / Known Bot Networks / IOCs.
- **`Incident`** (new table) - `timeline` is a JSON list of `{timestamp, actor, action, note}`
  entries rather than a normalized child table - it's an append-only log
  specific to one incident, never queried independently.
- **`auth/permissions.py`**: 7 new permissions (`reports:*`, `analytics:read`,
  `threat_intel:read`, `incidents:*`, `notifications:test`), granted to
  Security Analyst and (read-only) Viewer roles.
- **Real forward-compatibility bug found and fixed**: `seed_default_data()`
  previously skipped seeding entirely if *any* permission already existed
  in the database - meaning these 7 new permissions would never reach an
  already-Milestone-9-seeded deployment. Rewritten to add only what's
  missing (per permission, per role grant), verified with a two-seed-calls
  test simulating an upgrade.

## 8. Testing Guide

```bash
python -m pytest tests/reports/ tests/notifications/ tests/threat_intelligence/ tests/analytics/ tests/incidents/ tests/api/test_milestone10_routes.py -v
```

89 new backend tests (69 unit/service-level + 20 API-level), covering: every
report type generates without error in all three formats; the reputation
provider chain (fallback, provider-raises-doesn't-break-others, cache
hit/miss); the feed sync upsert logic; enrichment writing the tag onto the
correct alert row; every notification channel in isolation (mocked
SMTP/HTTP, never a real network call in tests) and via `NotificationManager`;
analytics composition including the honest `false_positive_rate: null`
placeholder; the incident state machine (valid/invalid transitions, timeline
append behavior); and, at the API layer, permission enforcement per role
(a Viewer can read incidents/reports but not create/generate them).

**All 298 pre-Milestone-10 backend tests still pass** (one pre-existing
test's assertion was updated to reflect Viewer's legitimately expanded
permission set — not a behavior change, a test catching up to an
intentional one). **All 22 pre-existing frontend tests still pass.**

## 9. Example PDF Report Structure

A generated PDF (`reportlab`-built, not HTML-rendered) contains: a title
page line, the report period and generation timestamp, then one heading +
table per section (e.g. "Top Attacks" → a table of attack type / count /
avg confidence; "Severity Distribution" → a two-column key/value table).
Verified end-to-end: `POST /reports/generate` with `format: "pdf"` returns
real, valid PDF bytes (`%PDF-...` header, opens as a normal document).

## 10. Example Analytics Response (`GET /analytics`)

```json
{
  "top_attack_types": {"DoS": 12, "PortScan": 5},
  "attack_timeline": [{"date": "2026-07-26", "count": 8}],
  "top_source_ips": [{"source_ip": "10.0.0.1", "count": 6}],
  "top_destination_ips": [{"destination_ip": "10.0.0.9", "count": 10}],
  "attack_heatmap": [{"day_of_week": 0, "hour": 14, "count": 3}],
  "severity_distribution": {"High": 10, "Low": 7},
  "detection_accuracy": 0.934,
  "false_positive_rate": null,
  "average_detection_time_ms": 4.8,
  "average_response_time_seconds": 12.3
}
```

## 11. Example Incident JSON

```json
{
  "id": "d8ea64ff-f4ef-4303-8c58-53d83c3f2388",
  "title": "Suspicious login from known-malicious IP",
  "description": "",
  "severity": "High",
  "priority": "High",
  "status": "assigned",
  "owner": "analyst1",
  "alert_id": null,
  "timeline": [
    {"timestamp": "2026-07-27T09:32:06+00:00", "actor": "admin", "action": "created", "note": "Incident opened: Suspicious login from known-malicious IP"},
    {"timestamp": "2026-07-27T09:33:10+00:00", "actor": "admin", "action": "status_changed", "note": "open -> assigned"},
    {"timestamp": "2026-07-27T09:33:10+00:00", "actor": "admin", "action": "assigned", "note": "Assigned to analyst1"}
  ],
  "created_by": "admin",
  "created_at": "2026-07-27T09:32:06+00:00",
  "updated_at": "2026-07-27T09:33:10+00:00",
  "closed_at": null
}
```

## 12. Milestone 10: Confirmed Complete

Verified live against the running server (not just unit-tested): every new
endpoint returns 200/201 as expected, threat-intel enrichment and automated
response both fire correctly for the same alert (`threat_tag: "Known
Malicious"`, `status: "responded"`), PDF/CSV/JSON export all produce real,
correctly-formatted output, and incident status transitions/timeline are
tracked exactly as designed.
