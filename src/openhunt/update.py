"""Auto-update and version checking against PyPI."""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import click

from openhunt import __version__
from openhunt.config import OPENHUNT_DIR, ensure_dirs

PYPI_PACKAGE = "openhunt-cli"
PYPI_URL = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"
CHECK_CACHE_PATH = OPENHUNT_DIR / "version_check.json"
CACHE_TTL = 24 * 3600  # 24 hours
REQUEST_TIMEOUT = 2.0  # seconds


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse version string into comparable tuple."""
    return tuple(int(x) for x in v.split("."))


def _is_major_bump(current: str, latest: str) -> bool:
    """Check if the update is a major version bump (e.g. 0.x → 1.x)."""
    cur = _parse_version(current)
    lat = _parse_version(latest)
    return lat[0] > cur[0]


def _load_cache() -> dict | None:
    """Load cached version check result."""
    if not CHECK_CACHE_PATH.exists():
        return None
    try:
        with open(CHECK_CACHE_PATH) as f:
            data = json.load(f)
        if time.time() - data.get("checked_at", 0) < CACHE_TTL:
            return data
    except (json.JSONDecodeError, ValueError, KeyError):
        pass
    return None


def _save_cache(latest: str) -> None:
    """Cache the latest version from PyPI."""
    ensure_dirs()
    with open(CHECK_CACHE_PATH, "w") as f:
        json.dump({"latest": latest, "checked_at": time.time()}, f)


def _fetch_latest_version() -> str | None:
    """Fetch the latest version from PyPI. Returns None on any error."""
    import httpx

    try:
        resp = httpx.get(PYPI_URL, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp.json()["info"]["version"]
    except Exception:
        return None


def _detect_installer() -> str | None:
    """Detect how openhunt was installed and return the upgrade command."""
    # Check uv tool
    if shutil.which("uv"):
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True, text=True, timeout=5,
        )
        if PYPI_PACKAGE in result.stdout:
            return "uv tool upgrade " + PYPI_PACKAGE

    # Check pipx
    if shutil.which("pipx"):
        result = subprocess.run(
            ["pipx", "list", "--short"],
            capture_output=True, text=True, timeout=5,
        )
        if PYPI_PACKAGE in result.stdout:
            return "pipx upgrade " + PYPI_PACKAGE

    # Fallback: pip
    return f"{sys.executable} -m pip install --upgrade {PYPI_PACKAGE}"


def _run_upgrade(cmd: str) -> bool:
    """Run the upgrade command. Returns True on success."""
    try:
        result = subprocess.run(
            cmd.split(), capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_and_update() -> None:
    """Check for updates and auto-update if possible.

    Called from the CLI main group callback. Designed to be non-disruptive:
    - Skips if not a terminal (CI, pipes)
    - Skips if cache is fresh (24h TTL)
    - Short timeout on PyPI request (2s)
    - Major version bumps: warn only, don't auto-update
    """
    # Don't show in non-interactive contexts
    if not sys.stderr.isatty():
        return

    # Check cache first
    cached = _load_cache()
    if cached:
        latest = cached["latest"]
    else:
        latest = _fetch_latest_version()
        if latest is None:
            return  # offline or timeout — silently continue
        _save_cache(latest)

    current = __version__

    if _parse_version(latest) <= _parse_version(current):
        return  # up to date

    cmd = _detect_installer()

    if _is_major_bump(current, latest):
        click.echo(
            f"Доступна новая мажорная версия: {latest} (текущая: {current})\n"
            f"  Обновить вручную: {cmd}",
            err=True,
        )
        return

    # Check if auto-update is enabled
    from openhunt.config import get_auto_update

    if not get_auto_update():
        click.echo(
            f"Доступна новая версия: {latest} (текущая: {current})\n"
            f"  Обновить: {cmd}",
            err=True,
        )
        return

    # Auto-update
    click.echo(
        f"Доступна новая версия: {latest} (текущая: {current})",
        err=True,
    )
    click.echo(f"  Обновляю...", err=True)

    if _run_upgrade(cmd):
        click.echo(f"  Обновлено до {latest}. Перезапустите команду.", err=True)
        raise SystemExit(0)
    else:
        click.echo(f"  Не удалось обновить. Обновите вручную: {cmd}", err=True)
