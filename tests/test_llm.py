"""Tests for LLM cover letter generation and questionnaire answering."""

import json
from unittest.mock import MagicMock, patch

import pytest

from openhunt.llm import (
    _parse_answers_response,
    answer_questions,
    generate_cover_letter,
    reset_client,
)


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


def test_codex_uses_responses_api(monkeypatch):
    from openhunt.config import set_llm_config
    set_llm_config("codex", model="gpt-5.4")

    # Simulate streaming: responses.create returns an iterable of events
    event = MagicMock()
    event.type = "response.output_text.delta"
    event.delta = "Codex-письмо."

    with patch("openhunt.auth.get_valid_codex_token", return_value="fake-token"):
        with patch("openhunt.llm.OpenAI") as mock_cls:
            mock_cls.return_value.responses.create.return_value = [event]
            result = generate_cover_letter("Dev", "Описание")

    assert result == "Codex-письмо."


def test_codex_returns_none_without_token(monkeypatch):
    from openhunt.config import set_llm_config
    set_llm_config("codex", model="gpt-5.4")

    with patch("openhunt.auth.get_valid_codex_token", return_value=None):
        result = generate_cover_letter("Dev", "Описание")

    assert result is None


# --- _parse_answers_response ---


_SAMPLE_QUESTIONS = [
    {"id": "q_aaa", "type": "text", "text": "Опыт с Python?"},
    {"id": "q_bbb", "type": "single_choice", "text": "Зарплата?"},
]


def test_parse_valid_json():
    raw = json.dumps([
        {"id": "q_aaa", "needs_human": False, "answer": {"text": "5 лет"}},
        {"id": "q_bbb", "needs_human": True, "answer": None},
    ])
    results = _parse_answers_response(raw, _SAMPLE_QUESTIONS)
    assert len(results) == 2
    assert results[0]["answer"] == {"text": "5 лет"}
    assert results[0]["needs_human"] is False
    assert results[1]["answer"] is None
    assert results[1]["needs_human"] is True


def test_parse_malformed_json_returns_all_needs_human():
    results = _parse_answers_response("not json at all", _SAMPLE_QUESTIONS)
    assert len(results) == 2
    assert all(r["needs_human"] is True for r in results)
    assert all(r["answer"] is None for r in results)


def test_parse_strips_markdown_fences():
    raw = '```json\n' + json.dumps([
        {"id": "q_aaa", "needs_human": False, "answer": {"text": "5 лет"}},
        {"id": "q_bbb", "needs_human": True, "answer": None},
    ]) + '\n```'
    results = _parse_answers_response(raw, _SAMPLE_QUESTIONS)
    assert results[0]["answer"] == {"text": "5 лет"}


def test_parse_missing_id_treated_as_needs_human():
    """If LLM returns fewer items than questions, missing ones get needs_human."""
    raw = json.dumps([
        {"id": "q_aaa", "needs_human": False, "answer": {"text": "5 лет"}},
    ])
    results = _parse_answers_response(raw, _SAMPLE_QUESTIONS)
    assert results[0]["needs_human"] is False
    assert results[1]["needs_human"] is True


def test_parse_non_list_returns_all_needs_human():
    raw = json.dumps({"error": "something went wrong"})
    results = _parse_answers_response(raw, _SAMPLE_QUESTIONS)
    assert all(r["needs_human"] is True for r in results)


# --- answer_questions ---


def test_answer_questions_no_config():
    """Without LLM configured, all questions are marked needs_human."""
    results = answer_questions(_SAMPLE_QUESTIONS)
    assert len(results) == 2
    assert all(r["needs_human"] is True for r in results)


def test_answer_questions_empty_list():
    assert answer_questions([]) == []


def test_answer_questions_calls_llm(monkeypatch):
    _setup_llm_config(monkeypatch)

    llm_response = json.dumps([
        {"id": "q_aaa", "needs_human": False, "answer": {"text": "5 лет"}},
        {"id": "q_bbb", "needs_human": True, "answer": None},
    ])

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = llm_response

    with patch("openhunt.llm.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value = mock_response
        results = answer_questions(_SAMPLE_QUESTIONS, profile_text="Python dev")

    assert results[0]["answer"] == {"text": "5 лет"}
    assert results[1]["needs_human"] is True


def test_answer_questions_api_error_returns_needs_human(monkeypatch):
    _setup_llm_config(monkeypatch)

    from openai import OpenAIError

    with patch("openhunt.llm.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.side_effect = OpenAIError("fail")
        results = answer_questions(_SAMPLE_QUESTIONS)

    assert all(r["needs_human"] is True for r in results)
