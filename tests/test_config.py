"""Tests for config management."""

import pytest

from openhunt.config import (
    load_config,
    save_config,
    get_default_resume,
    set_default_resume,
    get_cover_letter,
    set_cover_letter,
    reset_cover_letter,
    DEFAULT_COVER_LETTER,
    get_saved_queries,
    save_query,
    delete_query,
    CONFIG_PATH,
    OPENHUNT_DIR,
)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config to a temp directory for each test."""
    fake_dir = tmp_path / ".openhunt"
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", fake_dir)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", fake_dir / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", fake_dir / "config.toml")


def test_load_empty_config():
    assert load_config() == {}


def test_save_and_load_config():
    save_config({"key": "value"})
    assert load_config() == {"key": "value"}


def test_save_query():
    save_query("backend", "python AND django")
    assert get_saved_queries() == {"backend": "python AND django"}


def test_save_multiple_queries():
    save_query("backend", "python")
    save_query("ai", "machine learning")
    queries = get_saved_queries()
    assert queries == {"backend": "python", "ai": "machine learning"}


def test_overwrite_query():
    save_query("backend", "python")
    save_query("backend", "golang")
    assert get_saved_queries() == {"backend": "golang"}


def test_delete_query():
    save_query("backend", "python")
    assert delete_query("backend") is True
    assert get_saved_queries() == {}


def test_delete_nonexistent_query():
    assert delete_query("nope") is False


def test_delete_cleans_empty_section():
    save_query("only", "one")
    delete_query("only")
    config = load_config()
    assert "queries" not in config


def test_get_default_resume_empty():
    assert get_default_resume() is None


def test_set_and_get_default_resume():
    set_default_resume("abc123")
    assert get_default_resume() == "abc123"


def test_overwrite_default_resume():
    set_default_resume("old_id")
    set_default_resume("new_id")
    assert get_default_resume() == "new_id"


def test_get_cover_letter_default():
    assert get_cover_letter() == DEFAULT_COVER_LETTER


def test_set_cover_letter():
    set_cover_letter("Мой текст")
    assert get_cover_letter() == "Мой текст"


def test_reset_cover_letter():
    set_cover_letter("Мой текст")
    reset_cover_letter()
    assert get_cover_letter() == DEFAULT_COVER_LETTER
