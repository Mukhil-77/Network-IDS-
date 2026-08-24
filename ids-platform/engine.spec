# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the packaged SOC security engine (SOC-Engine.exe).

Build (from this directory, inside the venv):

    venv\Scripts\activate
    pip install pyinstaller
    python -m PyInstaller engine.spec --noconfirm \
        --distpath dist-engine --workpath build/engine-spec

Output: dist-engine/SOC-Engine/SOC-Engine.exe  (onedir build)

Everything the desktop Electron shell needs beyond the exe - the compiled
frontend and the default models - ships as separate extraResources in the
installer, so this spec bundles only Python code + data files that must sit
next to the modules that read them via Path(__file__).
"""

from PyInstaller.utils.hooks import collect_all

# Packages that import submodules dynamically or ship data/binaries.
# collect_all() gathers their __init__, submodules, data files and binaries
# in one call. Each is wrapped in try/except so an optional dependency that
# is missing locally degrades the bundle instead of failing the build.
_COLLECT_PACKAGES = [
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic",
    "pydantic_settings",
    "anyio",
    "sqlalchemy",
    "greenlet",
    "httpcore",
    "httpx",
    "requests",
    "PyYAML",
    "jwt",
    "bcrypt",
    "email_validator",
    "reportlab",
    "psutil",
    "joblib",
    "numpy",
    "pandas",
    "scipy",
    "sklearn",
    "imblearn",
    "scapy",
]

datas = []
binaries = []
hiddenimports = []

for pkg_name in _COLLECT_PACKAGES:
    try:
        d, b, h = collect_all(pkg_name)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        print(f"[engine.spec] package not found, skipping: {pkg_name}")

# Data files that must keep their package-relative layout so
# `Path(__file__).parent / "..."` lookups resolve inside the frozen app.
datas += [
    ("models", "models"),
    ("backend/threat_intelligence/data", "backend/threat_intelligence/data"),
    ("backend/notifications/config", "backend/notifications/config"),
    ("backend/response_engine/config", "backend/response_engine/config"),
]

a = Analysis(
    ["desktop_entry.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "test"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SOC-Engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SOC-Engine",
)