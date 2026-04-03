"""User configuration and data directory management."""

import tomllib
from pathlib import Path

import tomli_w

OPENHUNT_DIR = Path.home() / ".openhunt"
BROWSER_DIR = OPENHUNT_DIR / "browser"
CONFIG_PATH = OPENHUNT_DIR / "config.toml"


def ensure_dirs() -> None:
    OPENHUNT_DIR.mkdir(exist_ok=True)
    BROWSER_DIR.mkdir(exist_ok=True)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def save_config(config: dict) -> None:
    ensure_dirs()
    with open(CONFIG_PATH, "wb") as f:
        tomli_w.dump(config, f)


def get_default_resume() -> str | None:
    return load_config().get("resume")


def set_default_resume(resume_id: str) -> None:
    config = load_config()
    config["resume"] = resume_id
    save_config(config)


def get_saved_queries() -> dict[str, str]:
    return load_config().get("queries", {})


def save_query(name: str, query: str) -> None:
    config = load_config()
    config.setdefault("queries", {})[name] = query
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
