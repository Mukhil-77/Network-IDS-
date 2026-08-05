"""
OS-level telemetry for the System Health page's task-manager view.

Collects CPU, memory, disk, network, and (when available) GPU statistics via
psutil, plus this process's own resource usage. Network throughput is
reported as per-second rates computed from deltas between successive calls
(psutil's io_counters are cumulative), so the frontend can show live up/down
speeds like a task manager.

GPU support is best-effort: it shells out to `nvidia-smi` (standard NVIDIA
driver tooling on Windows/Linux) with a short timeout, and reports
`gpu: None` whenever the binary is missing, fails, or times out - so the
feature degrades gracefully on machines without an NVIDIA GPU, and the
frontend hides the GPU card rather than showing zeros.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

import psutil

from backend.utils.logger import get_logger

logger = get_logger(__name__)

NVIDIA_SMI_TIMEOUT_SECONDS = 2.0

# --------------------------------------------------------------------------
# Network-rate calculation: io_counters are cumulative totals, so the first
# call can't report a rate. Module-level state keeps the last counters +
# timestamp so successive calls can compute bytes-per-second deltas.
# --------------------------------------------------------------------------

_LAST_NET: dict[str, float] = {}
_LAST_NET_AT: Optional[float] = None


def _network_rates() -> dict[str, float]:
    """Per-second sent/received byte and packet rates across all interfaces."""
    global _LAST_NET, _LAST_NET_AT
    now = time.monotonic()
    counters = psutil.net_io_counters()
    totals = {
        "bytes_sent": float(counters.bytes_sent),
        "bytes_recv": float(counters.bytes_recv),
        "packets_sent": float(counters.packets_sent),
        "packets_recv": float(counters.packets_recv),
    }

    if _LAST_NET is None or _LAST_NET_AT is None:
        _LAST_NET, _LAST_NET_AT = totals, now
        return {
            "bytes_sent_per_sec": 0.0,
            "bytes_recv_per_sec": 0.0,
            "packets_sent_per_sec": 0.0,
            "packets_recv_per_sec": 0.0,
        }

    elapsed = max(now - _LAST_NET_AT, 1e-6)
    rates = {
        "bytes_sent_per_sec": max((totals["bytes_sent"] - _LAST_NET.get("bytes_sent", totals["bytes_sent"])) / elapsed, 0.0),
        "bytes_recv_per_sec": max((totals["bytes_recv"] - _LAST_NET.get("bytes_recv", totals["bytes_recv"])) / elapsed, 0.0),
        "packets_sent_per_sec": max((totals["packets_sent"] - _LAST_NET.get("packets_sent", totals["packets_sent"])) / elapsed, 0.0),
        "packets_recv_per_sec": max((totals["packets_recv"] - _LAST_NET.get("packets_recv", totals["packets_recv"])) / elapsed, 0.0),
    }
    _LAST_NET, _LAST_NET_AT = totals, now
    return rates


def _gpu_stats() -> Optional[dict]:
    """Best-effort NVIDIA GPU snapshot via nvidia-smi; None if unavailable."""
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return None
    try:
        result = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=NVIDIA_SMI_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        logger.debug("nvidia-smi query failed; GPU stats unavailable", exc_info=True)
        return None

    line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 4:
        return None

    try:
        return {
            "name": parts[0],
            "utilization_percent": float(parts[1]),
            "memory_used_mb": float(parts[2]),
            "memory_total_mb": float(parts[3]),
        }
    except ValueError:
        return None


def collect_system_stats() -> dict:
    """
    One point-in-time snapshot of the whole machine plus this process.
    Never raises: each subsystem is read defensively so a single failing
    probe (e.g. no permissions for disk usage) can't take the endpoint down.
    """
    snapshot: dict = {
        "timestamp": time.time(),
        "cpu": {},
        "memory": {},
        "disk": {},
        "network": {},
        "process": {},
        "gpu": None,
    }

    try:
        vm = psutil.virtual_memory()
        snapshot["memory"] = {
            "total_bytes": vm.total,
            "used_bytes": vm.used,
            "available_bytes": vm.available,
            "percent": vm.percent,
        }
        swap = psutil.swap_memory()
        snapshot["memory"]["swap_total_bytes"] = swap.total
        snapshot["memory"]["swap_used_bytes"] = swap.used
        snapshot["memory"]["swap_percent"] = swap.percent
    except Exception:  # noqa: BLE001
        logger.debug("Memory probe failed", exc_info=True)

    try:
        snapshot["cpu"] = {
            "percent": psutil.cpu_percent(interval=None),
            "logical_count": psutil.cpu_count(logical=True) or 0,
            "physical_count": psutil.cpu_count(logical=False) or 0,
            "per_core_percent": psutil.cpu_percent(interval=None, percpu=True),
        }
    except Exception:  # noqa: BLE001
        logger.debug("CPU probe failed", exc_info=True)

    try:
        disk = psutil.disk_usage(psutil.disk_partitions()[0].mountpoint if psutil.disk_partitions() else ".")
        snapshot["disk"] = {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": disk.percent,
        }
    except Exception:  # noqa: BLE001
        logger.debug("Disk probe failed", exc_info=True)

    try:
        snapshot["network"] = _network_rates()
    except Exception:  # noqa: BLE001
        logger.debug("Network probe failed", exc_info=True)

    try:
        proc = psutil.Process()
        snapshot["process"] = {
            "cpu_percent": proc.cpu_percent(interval=None),
            "memory_rss_bytes": proc.memory_info().rss,
            "threads": proc.num_threads(),
        }
    except Exception:  # noqa: BLE001
        logger.debug("Process probe failed", exc_info=True)

    snapshot["gpu"] = _gpu_stats()

    return snapshot
