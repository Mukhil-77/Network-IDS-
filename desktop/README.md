# SOC Platform - Windows Desktop Shell

Packages the existing SOC/network-security platform as a single Windows
desktop application (`SOC-Platform Setup.exe`). The Electron shell launches
the local Python security engine (the existing FastAPI/uvicorn backend,
bundled with PyInstaller), waits for it to become healthy, and opens the
existing React dashboard in an app window. The user never runs `uvicorn`,
`npm`, or `python` manually.

```
React + TypeScript + Tailwind UI  (ids-platform/frontend)
        | served by the engine (production) / Vite dev server (development)
        v
Electron shell  (desktop/)  <-- launches, monitors, shuts down everything
        |
        v
Local Python engine  (ids-platform -> PyInstaller -> SOC-Engine.exe)
        |
        +--> FastAPI API + WebSockets   backend/api/routes, backend/websocket
        +--> packet capture + detection + ML + threat intel + responses
        +--> SQLite database  (%LOCALAPPDATA%\SOC-Platform\data)
```

Nothing in the existing frontend or backend was rewritten - the desktop
layer only adds packaging/serving glue around them.

## Repository layout

| Path | Role |
| --- | --- |
| `ids-platform/` | The existing backend (FastAPI) + ML + security engine |
| `ids-platform/desktop_entry.py` | Engine entrypoint for packaged/dev runs |
| `ids-platform/engine.spec` | PyInstaller spec -> `SOC-Engine.exe` |
| `ids-platform/frontend/` | The single React/TS/Tailwind frontend (Vite) |
| `desktop/` | Electron shell (this directory) |
| `archive/soc-dashboard-frontend/` | Duplicate frontend, archived (superseded) |

## Requirements

- Windows 10/11 x64
- Node.js 20+ (for building; not needed to *run* the installed app)
- Python 3.14 installed, and the `ids-platform` virtualenv created with
  all requirements installed:
  ```powershell
  cd ids-platform
  python -m venv venv
  venv\Scripts\pip install -r requirements.txt
  ```
- Scapy packet capture additionally needs Npcap installed on the machine
  at runtime (capture just shows "unavailable" without it; everything else
  works).

## Development mode

```powershell
desktop\scripts\dev.ps1
```

This installs the Electron deps once, then starts (via `desktop/src/main.cjs`):

1. the backend engine  -> `venv\Scripts\python.exe desktop_entry.py` (127.0.0.1:8000)
2. the Vite dev server -> `npm run dev` in `ids-platform/frontend` (localhost:5173)
3. an Electron window loading the Vite server

Data/logs live under `desktop/.runtime/` in dev.
Set `SOC_DEV_TOOLS=1` to open DevTools on launch.

## Production build

One command produces the installer:

```powershell
desktop\scripts\build.ps1
```

It runs three stages:

| Stage | Command | Output |
| --- | --- | --- |
| 1. Engine | PyInstaller via `ids-platform\scripts\build_engine.ps1` | `ids-platform\dist-engine\SOC-Engine\SOC-Engine.exe` |
| 2. Frontend | `npm run build` in `ids-platform/frontend` | `ids-platform\frontend\dist` |
| 3. Desktop | `electron-builder --win` | `desktop\release\SOC-Platform-Setup-<ver>.exe` |

Stage 3 embeds the engine, the built frontend, default models, and the
editable YAML/JSON config defaults as `extraResources` (see
`electron-builder.yml`) and produces an NSIS installer.

### What the installer contains

- `resources\engine\SOC-Engine\` - the packaged Python engine
- `resources\frontend\` - the compiled React dashboard
- `resources\models\` - default trained model artifacts (v1..v4)
- `resources\defaults\` - default `response_rules.yaml`,
  `notification_rules.yaml`, `channel_settings.json`

### First run (installed app)

Electron creates a per-user runtime area `%LOCALAPPDATA%\SOC-Platform\`:

- `conf\app.env` - generated JWT secret + DB/model/config paths
  (generated locally, **never** shipped in the installer)
- `data\soc_platform.db` - SQLite database
- `data\models\` - writable copy of the default models
- `data\config\` - writable copies of the response/notification policies
- `logs\desktop.log`, `logs\backend.log` - diagnostics

The engine's response-policy and notification settings are *written* at
runtime (Policy Manager / Notification Settings UI), so those files get a
writable copy in user data; the backend resolves them via the
`RESPONSE_RULES_PATH`, `NOTIFICATION_RULES_PATH`, and
`CHANNEL_SETTINGS_PATH` environment variables.

## Configuration & secrets

- No credentials are baked into the installer. JWT secrets are generated on
  first run. SMTP/Telegram/webhook credentials are entered via the
  Notification Settings UI and stored in the user-data
  `channel_settings.json`.
- `ENABLE_LIVE_RESPONSE_ACTIONS` stays disabled unless a local operator
  deliberately enables it (the existing hard safety gate is preserved).

## Adding a custom icon

Place `desktop/build/icon.ico` (256x256) before running `build.ps1`; the
`win.icon` default is picked up automatically by electron-builder.

## Troubleshooting

- App window opens but shows an error/retry page: the backend is usually
  still loading the trained model on first start; check
  `%LOCALAPPDATA%\SOC-Platform\logs\backend.log`.
- "Engine did not start": read `logs\backend.log` for the traceback.
- Windows SmartScreen warning on the unsigned installer: expected until the
  app is code-signed (add signing config under `win.signAndEditExecutable`
  in `electron-builder.yml`).