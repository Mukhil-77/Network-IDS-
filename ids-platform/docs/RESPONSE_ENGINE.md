# Automated Response Engine (Milestone 8)

Transforms the IDS into an IDR (Intelligent Detection and Response)
platform: every detected threat automatically triggers a configurable set
of response actions, safely, with full audit history and rollback support.

## 1. Response Workflow

```
Threat Detected                    (AlertService persists an alert - Milestone 6)
    │
    ▼
Determine Severity                 (the persisted alert's severity field)
    │
    ▼
Select Response Policy             (PolicyEngine.get_actions(severity), from response_rules.yaml)
    │
    ▼
Execute Actions                    (response_executor.execute_actions - one action failing
    │                                doesn't stop the rest)
    ▼
Record Result                      (one ResponseHistory row per action)
    │
    ▼
Update Alert Status                (Alert.status -> responded / partially_responded / response_failed)
    │
    ▼
Notify Dashboard                   (WebSocket: response_started -> response_completed/failed per action)
```

Two ways this workflow runs:
- **Automatic** — `AlertService.on_alert_persisted` (one additive callback,
  mirroring Milestone 5's `on_flow_closed` pattern) fires
  `ResponseService.handle_alert()` for every persisted alert, wired in
  `main.py`'s lifespan. Nothing about detection or alerting was duplicated
  or modified to make this work.
- **Manual** — `POST /responses/execute`, for an analyst to re-run or
  override a response for a specific alert.

## 2. Policy Engine

`backend/response_engine/response_rules.py`'s `PolicyEngine` loads
severity → ordered-action-list mappings from
`backend/response_engine/config/response_rules.yaml` (JSON/YAML per spec —
YAML chosen for readability and comment support). Default:

```yaml
simulation_mode: true
policies:
  Critical: [block_ip, quarantine_host, send_email, send_telegram, log_response]
  High:     [block_ip, restart_service, generate_incident]
  Medium:   [notify_analyst, increase_monitoring]
  Low:      [log_response]
```

`GET /response-rules` returns the live config; `PUT /response-rules`
validates every action name against the registry (rejecting unknown
actions with 400) and rewrites the YAML file, so changes survive a
restart.

## 3. Action Registry (extensibility)

`response_registry.py` is the single place an action is registered:

```python
def my_action(context: ResponseContext) -> ActionResult:
    ...
register_action("my_action", my_action, rollback_of="some_other_action")
```

Adding a new action means writing one function — nothing else in the
engine changes. Currently registered: `block_ip`, `unblock_ip`,
`quarantine_host`, `unquarantine_host`, `restart_service`, `kill_process`,
`send_email`, `send_telegram`, `webhook_notification`, `log_response`,
`generate_incident`, `notify_analyst`, `increase_monitoring`.

## 4. Simulation Mode & Safety

**"Do NOT execute destructive actions by default" is enforced
structurally, not by convention** — `simulation.py`'s `resolve_mode()` is
the one place every action checks before doing anything live, and it
requires **two independent gates to both agree**:

1. The policy/API caller requested `mode="live"`.
2. `Settings.ENABLE_LIVE_RESPONSE_ACTIONS` is `true` — an environment
   variable an operator sets, never a policy file or an API request.

If either says no, the action **simulates**: it logs exactly what it would
have done and returns success, without touching a firewall, process,
service, or sending a real notification. This means a misconfigured policy
or a stray API call can never take a destructive real-world action by
accident — enabling live actions is a deliberate, separate, operator-only
decision.

Two actions go further and are **always** simulated regardless of any
flag: `quarantine_host`/`unquarantine_host` have no live implementation at
all (network-layer isolation is outside what this project can reach into —
see `quarantine.py`'s docstring for why that's an honest gap, not a
shortcut).

## 5. Recovery / Rollback

Only actions with a real inverse are rollback-eligible:
`block_ip → unblock_ip`, `quarantine_host → unquarantine_host`.
`restart_service`/`kill_process`/notifications have no sensible rollback
("un-restart" isn't a thing) and correctly report
`rollback_available=False`.

`POST /responses/rollback` looks up the original `ResponseHistory` row,
finds its registered rollback action, executes it, marks the original
`rolled_back=True`, and records the rollback itself as a new
`ResponseHistory` row (so the rollback is just as audited as the original
action).

**A real bug was found and fixed while testing this**: the first
implementation executed the rollback action while still holding open the
database session that fetched the original record — but several action
handlers (`unblock_ip`, `log_response`, etc.) open their *own* database
session. Nesting them caused the outer transaction to be silently
committed and closed partway through, so `rolled_back=True` never
persisted. Fixed by restructuring `rollback()` into three separate, short
sessions (read → execute action with no session held open → write) — the
same pattern `_run()` already used correctly. Covered by a regression test
(`test_rollback_twice_raises`).

## 6. Security Considerations

- **No destructive action runs without an explicit operator opt-in**
  (`ENABLE_LIVE_RESPONSE_ACTIONS`) — see §4.
- **Every action is audited**: who (`operator` — `"automated"` or an
  analyst identifier), when (`timestamp`), what (`action`), the result
  (`status`, `message`), and how long it took (`execution_time_ms`) — one
  `ResponseHistory` row per action, queryable via `GET /responses`.
- **Live actions are narrowly scoped**: `block_ip`'s live path only ever
  adds/removes one `iptables DROP` rule for one source IP — it cannot
  affect anything else on the host, and fails closed (returns `status:
  "failed"`, doesn't raise) if `iptables` isn't available.
- **No action can crash the response workflow**: every handler call is
  wrapped (`response_executor.py`), so one failing action (e.g. a real SMTP
  timeout) never prevents the rest of the policy from running or the alert
  status from being updated.
- **Policy changes are validated before being applied**: `PUT
  /response-rules` rejects (400) any policy referencing an unregistered
  action, so a typo can't silently create a no-op policy.

## 7. Example Response Workflow

```
1. DetectionService classifies a flow: DDoS, Critical, confidence=98.5%
2. AlertService persists the Alert + FlowHistory, broadcasts "alert" over WebSocket
3. AlertService.on_alert_persisted fires -> ResponseService.handle_alert()
4. PolicyEngine.get_actions("Critical") -> [block_ip, quarantine_host, send_email, send_telegram, log_response]
5. WebSocket: "response_started" broadcast (5 actions, mode=simulation)
6. Each action executes in order; each broadcasts "response_completed" (or "response_failed")
7. 5 ResponseHistory rows written, alert.status -> "responded"
8. Dashboard's Response Center / Response History pages update instantly (no polling)
```

## 8. Example Response History (`GET /responses/{id}`)

```json
{
  "id": "ea0d2810-44bb-4b47-bac2-3e1e76239d53",
  "response_group_id": "1a67fde9-439a-4c01-9493-49bfe7b5049a",
  "alert_id": "9ef2ac28-1515-4b6b-af86-a7a9c5dcf0c2",
  "action": "generate_incident",
  "status": "success",
  "message": "Incident #8 created",
  "execution_time_ms": 3.93,
  "operator": "analyst",
  "mode": "simulation",
  "rollback_available": false,
  "rolled_back": false,
  "timestamp": "2026-07-25T12:31:32.234517"
}
```

## 9. Testing

```bash
python -m pytest tests/response_engine/ tests/api/test_responses_routes.py -v
```

57 tests: policy loading/evaluation/persistence, action registry &
rollback-mapping, executor fault-isolation, every individual action handler
in simulation mode (verified via mocking that **no real subprocess/SMTP/
HTTP call is ever made** in simulation), the full `ResponseService`
workflow (severity → policy → execution → status update), rollback
(including the regression test for the bug above), and every REST endpoint.

## 10. Files Added / Modified

**Added**: `backend/response_engine/*` (10 files), `backend/database/repositories/responses.py`,
`backend/api/routes/responses.py`, `tests/response_engine/*`, `tests/api/test_responses_routes.py`,
3 new frontend pages + supporting service/hook/types/component.

**Modified (all additive or bug fixes, flagged individually in code)**:
- `backend/database/models.py` — added `ResponseHistory` table
- `backend/database/connection.py` — **bug fix**: `expire_on_commit=False`
  (any ORM object returned out of `session_scope()` was unusable the
  moment a caller read it - a latent bug, not specific to this milestone,
  exposed by response_service.py's legitimate need to read a row's `id`
  after its session closed)
- `backend/services/alert_service.py` — added optional `on_alert_persisted` callback
- `backend/websocket/events.py`, `broadcaster.py` — generalized from
  alert-only to any event type (backward-compatible wrappers kept)
- `backend/core/config.py` — added response engine settings
- `backend/main.py` — wired the response engine into startup
- `backend/api/routes/__init__.py`, `backend/api/schemas.py` — registered new router/schemas
- `tests/api/conftest.py` — aligned test session config with the connection.py fix above
