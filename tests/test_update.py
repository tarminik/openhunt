"""Tests for auto-update and version checking."""

import json
import time

import pytest

from openhunt.config import invalidate_config_cache
from openhunt.update import (
    _detect_installer,
    _is_major_bump,
    _load_cache,
    _parse_version,
    _save_cache,
)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config and cache to temp directory."""
    invalidate_config_cache()
    fake_dir = tmp_path / ".openhunt"
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", fake_dir)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", fake_dir / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", fake_dir / "config.toml")
    monkeypatch.setattr("openhunt.update.OPENHUNT_DIR", fake_dir)
    monkeypatch.setattr("openhunt.update.CHECK_CACHE_PATH", fake_dir / "version_check.json")


# --- Version parsing ---


def test_parse_version():
    assert _parse_version("0.3.0") == (0, 3, 0)
    assert _parse_version("1.0.0") == (1, 0, 0)
    assert _parse_version("0.10.2") == (0, 10, 2)


def test_parse_version_comparison():
    assert _parse_version("0.4.0") > _parse_version("0.3.0")
    assert _parse_version("1.0.0") > _parse_version("0.99.99")
    assert _parse_version("0.3.0") == _parse_version("0.3.0")


def test_is_major_bump():
    assert _is_major_bump("0.3.0", "1.0.0") is True
    assert _is_major_bump("1.0.0", "2.0.0") is True
    assert _is_major_bump("0.3.0", "0.4.0") is False
    assert _is_major_bump("0.3.0", "0.3.1") is False


# --- Cache ---


def test_save_and_load_cache():
    _save_cache("0.4.0")
    cached = _load_cache()
    assert cached is not None
    assert cached["latest"] == "0.4.0"


def test_load_cache_empty():
    assert _load_cache() is None


def test_load_cache_expired(tmp_path, monkeypatch):
    cache_path = tmp_path / ".openhunt" / "version_check.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("openhunt.update.CHECK_CACHE_PATH", cache_path)

    with open(cache_path, "w") as f:
        json.dump({"latest": "0.4.0", "checked_at": time.time() - 90000}, f)

    assert _load_cache() is None


def test_load_cache_corrupted(tmp_path, monkeypatch):
    cache_path = tmp_path / ".openhunt" / "version_check.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("openhunt.update.CHECK_CACHE_PATH", cache_path)

    cache_path.write_text("not json")
    assert _load_cache() is None


# --- check_and_update ---


def test_check_and_update_skips_non_tty(monkeypatch):
    """Should silently return when stderr is not a terminal."""
    from openhunt.update import check_and_update

    monkeypatch.setattr("sys.stderr", type("FakeStderr", (), {"isatty": lambda self: False})())
    # Should not raise or print anything
    check_and_update()


def test_check_and_update_up_to_date(monkeypatch):
    """Should do nothing when already on latest version."""
    from openhunt import update
    from openhunt.update import check_and_update

    monkeypatch.setattr("sys.stderr", type("FakeStderr", (), {"isatty": lambda self: True})())
    monkeypatch.setattr(update, "_fetch_latest_version", lambda: "0.3.0")
    monkeypatch.setattr(update, "__version__", "0.3.0")

    check_and_update()  # should not raise


def test_check_and_update_warns_major_bump(monkeypatch, capsys):
    """Major version bumps should only warn, not auto-update."""
    from openhunt import update
    from openhunt.update import check_and_update

    monkeypatch.setattr("sys.stderr", type("FakeStderr", (), {"isatty": lambda self: True, "write": lambda self, s: None, "flush": lambda self: None})())
    monkeypatch.setattr(update, "_fetch_latest_version", lambda: "1.0.0")
    monkeypatch.setattr(update, "__version__", "0.3.0")
    monkeypatch.setattr(update, "_detect_installer", lambda: "uv tool upgrade openhunt-cli")

    check_and_update()
    # Should not have called _run_upgrade — we verify by checking no SystemExit was raised


def test_check_and_update_offline(monkeypatch):
    """Should silently continue when PyPI is unreachable."""
    from openhunt import update
    from openhunt.update import check_and_update

    monkeypatch.setattr("sys.stderr", type("FakeStderr", (), {"isatty": lambda self: True})())
    monkeypatch.setattr(update, "_fetch_latest_version", lambda: None)

    check_and_update()  # should not raise


def test_check_and_update_uses_cache(monkeypatch):
    """Should use cached value instead of fetching."""
    from openhunt import update
    from openhunt.update import check_and_update

    monkeypatch.setattr("sys.stderr", type("FakeStderr", (), {"isatty": lambda self: True})())
    monkeypatch.setattr(update, "__version__", "0.3.0")

    _save_cache("0.3.0")

    fetch_called = []
    original_fetch = update._fetch_latest_version
    def mock_fetch():
        fetch_called.append(True)
        return original_fetch()
    monkeypatch.setattr(update, "_fetch_latest_version", mock_fetch)

    check_and_update()
    assert len(fetch_called) == 0


# --- CLI commands ---


def test_update_on_off(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from openhunt.cli import main

    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    runner = CliRunner()

    result = runner.invoke(main, ["--no-update", "update", "off"])
    assert result.exit_code == 0
    assert "выключено" in result.output

    result = runner.invoke(main, ["--no-update", "update", "status"])
    assert "выключено" in result.output

    result = runner.invoke(main, ["--no-update", "update", "on"])
    assert result.exit_code == 0
    assert "включено" in result.output

    result = runner.invoke(main, ["--no-update", "update", "status"])
    assert "включено" in result.output


def test_update_check_up_to_date(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from openhunt.cli import main
    from openhunt import update

    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setattr("openhunt.update.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.update.CHECK_CACHE_PATH", tmp_path / "version_check.json")
    monkeypatch.setattr(update, "_fetch_latest_version", lambda: "0.3.0")

    runner = CliRunner()
    result = runner.invoke(main, ["--no-update", "update", "check"])
    assert result.exit_code == 0
    assert "последняя версия" in result.output.lower() or "0.3.0" in result.output
