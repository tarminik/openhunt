"""Tests for LLM cover letter generation."""

from unittest.mock import MagicMock, patch

import pytest

from openhunt.llm import generate_cover_letter, reset_client


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config to a temp directory for each test."""
    reset_client()
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")


def _setup_llm_config(monkeypatch, provider="openrouter", api_key="sk-test", model="gpt-4"):
    from openhunt.config import set_llm_config
    set_llm_config(provider, api_key, model)


def test_returns_none_when_not_configured():
    assert generate_cover_letter("Title", "Description") is None


def test_returns_generated_text(monkeypatch):
    _setup_llm_config(monkeypatch)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Сгенерированное письмо."

    with patch("openhunt.llm.OpenAI") as mock_client_cls:
        mock_client_cls.return_value.chat.completions.create.return_value = mock_response
        result = generate_cover_letter("Python Developer", "Описание вакансии")

    assert result == "Сгенерированное письмо."


def test_returns_none_on_api_error(monkeypatch):
    _setup_llm_config(monkeypatch)

    from openai import OpenAIError

    with patch("openhunt.llm.OpenAI") as mock_client_cls:
        mock_client_cls.return_value.chat.completions.create.side_effect = OpenAIError("fail")
        result = generate_cover_letter("Title", "Description")

    assert result is None


def test_returns_none_on_empty_choices(monkeypatch):
    _setup_llm_config(monkeypatch)

    mock_response = MagicMock()
    mock_response.choices = []

    with patch("openhunt.llm.OpenAI") as mock_client_cls:
        mock_client_cls.return_value.chat.completions.create.return_value = mock_response
        result = generate_cover_letter("Title", "Description")

    assert result is None


def test_returns_none_on_empty_content(monkeypatch):
    _setup_llm_config(monkeypatch)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = None

    with patch("openhunt.llm.OpenAI") as mock_client_cls:
        mock_client_cls.return_value.chat.completions.create.return_value = mock_response
        result = generate_cover_letter("Title", "Description")

    assert result is None


def test_returns_none_on_constructor_error(monkeypatch):
    _setup_llm_config(monkeypatch)

    with patch("openhunt.llm.OpenAI", side_effect=Exception("bad config")):
        result = generate_cover_letter("Title", "Description")

    assert result is None


def test_returns_none_for_custom_without_base_url(monkeypatch):
    from openhunt.config import set_llm_config
    set_llm_config("custom", "sk-test", "model", base_url="https://example.com/v1")
    # Now break it by removing base_url manually
    from openhunt.config import load_config, save_config
    config = load_config()
    del config["llm"]["base_url"]
    save_config(config)

    result = generate_cover_letter("Title", "Description")
    assert result is None
