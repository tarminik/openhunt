"""User configuration and data directory management."""

import copy
import json
import tomllib
from pathlib import Path

import tomli_w

OPENHUNT_DIR = Path.home() / ".openhunt"
BROWSER_DIR = OPENHUNT_DIR / "browser"
CONFIG_PATH = OPENHUNT_DIR / "config.toml"
AUTH_PATH = OPENHUNT_DIR / "auth.json"

_config_cache: dict | None = None


def ensure_dirs() -> None:
    OPENHUNT_DIR.mkdir(mode=0o700, exist_ok=True)
    BROWSER_DIR.mkdir(mode=0o700, exist_ok=True)


def invalidate_config_cache() -> None:
    """Reset the in-memory config cache, forcing the next load_config() to read from disk."""
    global _config_cache
    _config_cache = None


def load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return copy.deepcopy(_config_cache)
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "rb") as f:
        _config_cache = tomllib.load(f)
    return copy.deepcopy(_config_cache)


def save_config(config: dict) -> None:
    ensure_dirs()
    with open(CONFIG_PATH, "wb") as f:
        tomli_w.dump(config, f)
    CONFIG_PATH.chmod(0o600)
    invalidate_config_cache()


def get_default_resume() -> str | None:
    return load_config().get("resume")


def set_default_resume(resume_id: str) -> None:
    config = load_config()
    config["resume"] = resume_id
    save_config(config)


DEFAULT_COVER_LETTER = (
    "Здравствуйте. Меня заинтересовала вакансия. Хотел бы обсудить подробнее."
)


def get_cover_letter() -> str:
    return load_config().get("cover_letter", DEFAULT_COVER_LETTER)


def set_cover_letter(text: str) -> None:
    config = load_config()
    config["cover_letter"] = text
    save_config(config)


def reset_cover_letter() -> None:
    config = load_config()
    config.pop("cover_letter", None)
    save_config(config)


def get_saved_queries() -> dict[str, str]:
    return load_config().get("queries", {})


def save_query(name: str, query: str) -> None:
    config = load_config()
    config.setdefault("queries", {})[name] = query
    save_config(config)


def get_llm_config() -> dict | None:
    """Return LLM config dict or None if not configured.

    For codex provider, only model and provider are required (auth via OAuth).
    For other providers, api_key is also required.
    """
    config = load_config()
    llm = config.get("llm")
    if not llm:
        return None
    if not llm.get("provider") or not llm.get("model"):
        return None
    if llm["provider"] != "codex" and not llm.get("api_key"):
        return None
    return llm


def set_llm_config(
    provider: str, api_key: str | None = None, model: str = "", base_url: str | None = None,
) -> None:
    config = load_config()
    llm: dict = {"provider": provider, "model": model}
    if api_key:
        llm["api_key"] = api_key
    if base_url:
        llm["base_url"] = base_url
    config["llm"] = llm
    save_config(config)


def reset_llm_config() -> None:
    config = load_config()
    config.pop("llm", None)
    save_config(config)


def get_letter_strategy() -> str | None:
    """Return the saved letter strategy, or None if not set."""
    return load_config().get("letter_strategy")


def set_letter_strategy(strategy: str) -> None:
    """Save the letter strategy to config."""
    config = load_config()
    config["letter_strategy"] = strategy
    save_config(config)


def delete_query(name: str) -> bool:
    config = load_config()
    if "queries" in config and name in config["queries"]:
        del config["queries"][name]
        if not config["queries"]:
            del config["queries"]
        save_config(config)
        return True
    return False


# --- Auth token storage (auth.json) ---


def load_auth() -> dict:
    """Load auth tokens from auth.json."""
    if not AUTH_PATH.exists():
        return {}
    with open(AUTH_PATH) as f:
        return json.load(f)


def save_auth(auth: dict) -> None:
    """Save auth tokens to auth.json with restricted permissions."""
    ensure_dirs()
    with open(AUTH_PATH, "w") as f:
        json.dump(auth, f, indent=2)
    AUTH_PATH.chmod(0o600)


def get_codex_tokens() -> dict | None:
    """Return codex tokens dict or None if not stored."""
    auth = load_auth()
    tokens = auth.get("codex")
    if not tokens or not tokens.get("access_token") or not tokens.get("refresh_token"):
        return None
    return tokens


def save_codex_tokens(access_token: str, refresh_token: str) -> None:
    """Save codex OAuth tokens."""
    auth = load_auth()
    auth["codex"] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }
    save_auth(auth)


def reset_codex_tokens() -> None:
    """Remove codex tokens from auth store."""
    auth = load_auth()
    auth.pop("codex", None)
    save_auth(auth)
