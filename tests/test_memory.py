"""Tests for memory storage."""

import time

import pytest

from openhunt.memory import (
    get_profile,
    save_profile,
    profile_needs_sync,
    PROFILES_PATH,
    MEMORY_DIR,
    PROFILE_MAX_AGE_HOURS,
)


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """Redirect memory to a temp directory for each test."""
    fake_dir = tmp_path / "memory"
    monkeypatch.setattr("openhunt.memory.MEMORY_DIR", fake_dir)
    monkeypatch.setattr("openhunt.memory.PROFILES_PATH", fake_dir / "profiles.json")


def test_get_profile_empty():
    assert get_profile("abc123") is None


def test_save_and_get_profile():
    save_profile("abc123", "Python developer, 5 years experience")
    assert get_profile("abc123") == "Python developer, 5 years experience"


def test_save_multiple_profiles():
    save_profile("abc", "Profile A")
    save_profile("def", "Profile B")
    assert get_profile("abc") == "Profile A"
    assert get_profile("def") == "Profile B"


def test_overwrite_profile():
    save_profile("abc", "Old text")
    save_profile("abc", "New text")
    assert get_profile("abc") == "New text"


def test_profile_needs_sync_missing():
    assert profile_needs_sync("abc123") is True


def test_profile_needs_sync_fresh():
    save_profile("abc123", "Fresh profile")
    assert profile_needs_sync("abc123") is False


def test_profile_needs_sync_stale(monkeypatch):
    save_profile("abc123", "Stale profile")
    # Make the profile appear old
    stale_time = time.time() - (PROFILE_MAX_AGE_HOURS + 1) * 3600
    from openhunt.memory import _load_profiles, _save_profiles
    profiles = _load_profiles()
    profiles["abc123"]["synced_at"] = stale_time
    _save_profiles(profiles)

    assert profile_needs_sync("abc123") is True
