"""
Windows desktop-app engine entrypoint (packaged with PyInstaller as
SOC-Engine.exe).

Spawned by the Electron shell (see desktop/ in the repository root). Takes
its host/port/log level from the SOC_* environment variables the shell sets,
then boots the existing FastAPI app with uvicorn and serves the built React
frontend from FRONTEND_DIST when that setting points at a real directory.

Imports live at module scope (not inside main()) on purpose: PyInstaller's
static analysis follows top-level imports, so importing `backend.main.app`
here is what pulls the entire backend dependency graph into the bundle at
build time.

Dev mode uses this same entrypoint: the desktop dev script runs it with the
venv Python interpreter, so there is a single code path for "start the
engine" everywhere.
"""

from __future__ import annotations

import os

from backend.main import app

_HOST = os.environ.get("SOC_HOST", "127.0.0.1")
_PORT = int(os.environ.get("SOC_PORT", "8000"))
_LOG_LEVEL = os.environ.get("SOC_LOG_LEVEL", "info").lower()

ENGINE_VERSION = "1.0.0"


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=_HOST,
        port=_PORT,
        log_level=_LOG_LEVEL,
        access_log=_LOG_LEVEL not in ("critical", "fatal"),
        timeout_keep_alive=30,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()