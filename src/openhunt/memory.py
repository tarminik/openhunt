"""Local memory storage for user profiles and future questionnaire answers."""

import json
import time
from pathlib import Path

from openhunt.config import OPENHUNT_DIR

MEMORY_DIR = OPENHUNT_DIR / "memory"
PROFILES_PATH = MEMORY_DIR / "profiles.json"
PROFILE_MAX_AGE_HOURS = 7 * 24  # 7 days


def _ensure_memory_dir() -> None:
    MEMORY_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)


def _load_profiles() -> dict:
    if not PROFILES_PATH.exists():
        return {}
    with open(PROFILES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_profiles(profiles: dict) -> None:
    _ensure_memory_dir()
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    PROFILES_PATH.chmod(0o600)


def get_profile(resume_id: str) -> str | None:
    """Return stored profile text for the given resume ID, or None."""
    profiles = _load_profiles()
    entry = profiles.get(resume_id)
    if entry:
        return entry.get("text")
    return None


def get_user_name() -> str | None:
    """Return stored user name, or None."""
    profiles = _load_profiles()
    return profiles.get("_user_name")


def save_profile(resume_id: str, text: str, user_name: str | None = None) -> None:
    """Save profile text with current timestamp and optionally the user name."""
    profiles = _load_profiles()
    profiles[resume_id] = {
        "text": text,
        "synced_at": time.time(),
    }
    if user_name:
        profiles["_user_name"] = user_name
    _save_profiles(profiles)


def profile_needs_sync(resume_id: str) -> bool:
    """Check if profile is missing or older than PROFILE_MAX_AGE_HOURS."""
    profiles = _load_profiles()
    entry = profiles.get(resume_id)
    if not entry:
        return True
    synced_at = entry.get("synced_at", 0)
    age_hours = (time.time() - synced_at) / 3600
    return age_hours >= PROFILE_MAX_AGE_HOURS
