"""Tests for CLI argument validation."""

import pytest
from click.testing import CliRunner

from importlib.metadata import version

from openhunt.cli import main
from openhunt.config import invalidate_config_cache


runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """Invalidate config cache before each test to avoid stale data."""
    invalidate_config_cache()


def test_version():
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert version("openhunt-cli") in result.output


def test_verbose_flag_accepted():
    result = runner.invoke(main, ["--verbose", "--version"])
    assert result.exit_code == 0


def test_apply_no_source():
    result = runner.invoke(main, ["apply", "--resume", "abc123"])
    assert result.exit_code != 0
    assert "Укажите --query, --saved или --recommended" in result.output


def test_apply_multiple_sources():
    result = runner.invoke(main, ["apply", "--resume", "abc123", "--query", "python", "--recommended"])
    assert result.exit_code != 0
    assert "Укажите только один из" in result.output


def test_apply_no_resume_no_default(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["apply", "--query", "python"])
    assert result.exit_code != 0
    assert "resume" in result.output.lower()


def test_apply_saved_nonexistent(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["apply", "--resume", "abc123", "--saved", "nope"])
    assert result.exit_code != 0
    assert "не найден" in result.output


def test_resume_set_and_show(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["resume", "set", "abc123"])
    assert result.exit_code == 0
    assert "abc123" in result.output

    result = runner.invoke(main, ["resume", "show"])
    assert result.exit_code == 0
    assert "abc123" in result.output


def test_resume_show_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["resume", "show"])
    assert result.exit_code == 0
    assert "не задано" in result.output


def test_apply_uses_default_resume(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    captured = {}
    def fake_apply(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openhunt.browser.actions.apply.apply_to_vacancies", fake_apply)

    runner.invoke(main, ["resume", "set", "saved_id"])
    runner.invoke(main, ["apply", "--query", "python"])
    assert captured["resume_id"] == "saved_id"


def test_apply_explicit_resume_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    captured = {}
    def fake_apply(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openhunt.browser.actions.apply.apply_to_vacancies", fake_apply)

    runner.invoke(main, ["resume", "set", "saved_id"])
    runner.invoke(main, ["apply", "--resume", "explicit_id", "--query", "python"])
    assert captured["resume_id"] == "explicit_id"


def test_letter_show_default(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["letter", "show"])
    assert result.exit_code == 0
    assert "Здравствуйте" in result.output


def test_letter_set_and_show(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["letter", "set", "Мой текст"])
    assert result.exit_code == 0
    assert "сохранён" in result.output

    result = runner.invoke(main, ["letter", "show"])
    assert "Мой текст" in result.output


def test_letter_reset(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    runner.invoke(main, ["letter", "set", "Мой текст"])
    result = runner.invoke(main, ["letter", "reset"])
    assert result.exit_code == 0

    result = runner.invoke(main, ["letter", "show"])
    assert "Здравствуйте" in result.output


def test_query_save_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["query", "save", "test", "python developer"])
    assert result.exit_code == 0
    assert "сохранён" in result.output

    result = runner.invoke(main, ["query", "list"])
    assert result.exit_code == 0
    assert "test" in result.output
    assert "python developer" in result.output


def test_query_delete(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    runner.invoke(main, ["query", "save", "test", "python"])
    result = runner.invoke(main, ["query", "delete", "test"])
    assert result.exit_code == 0
    assert "удалён" in result.output


def test_llm_setup_openrouter(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, [
        "llm", "setup",
        "--provider", "openrouter",
        "--api-key", "sk-test-123",
        "--model", "anthropic/claude-sonnet-4-20250514",
    ])
    assert result.exit_code == 0
    assert "LLM настроен" in result.output


def test_llm_setup_custom_requires_base_url(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, [
        "llm", "setup",
        "--provider", "custom",
        "--api-key", "sk-test",
        "--model", "my-model",
    ])
    assert result.exit_code != 0
    assert "base-url" in result.output.lower() or "base_url" in result.output.lower()


def test_llm_show_and_reset(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    runner.invoke(main, [
        "llm", "setup",
        "--provider", "openrouter",
        "--api-key", "sk-test-key-12345678",
        "--model", "gpt-4",
    ])
    result = runner.invoke(main, ["llm", "show"])
    assert result.exit_code == 0
    assert "openrouter" in result.output
    assert "gpt-4" in result.output
    assert "sk-test-key-12345678" not in result.output  # key masked

    result = runner.invoke(main, ["llm", "reset"])
    assert result.exit_code == 0

    result = runner.invoke(main, ["llm", "show"])
    assert "не настроен" in result.output


def test_llm_show_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["llm", "show"])
    assert result.exit_code == 0
    assert "не настроен" in result.output


def test_apply_dry_run_flag(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    captured = {}
    def fake_apply(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openhunt.browser.actions.apply.apply_to_vacancies", fake_apply)

    runner.invoke(main, ["resume", "set", "abc123"])

    # Without --dry-run
    runner.invoke(main, ["apply", "--query", "python"])
    assert captured["dry_run"] is False

    # With --dry-run
    runner.invoke(main, ["apply", "--query", "python", "--dry-run"])
    assert captured["dry_run"] is True


def test_apply_default_strategy_without_llm(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    captured = {}
    def fake_apply(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openhunt.browser.actions.apply.apply_to_vacancies", fake_apply)

    runner.invoke(main, ["resume", "set", "abc123"])
    runner.invoke(main, ["apply", "--query", "python"])

    from openhunt.browser.actions.apply import LetterStrategy
    assert captured["letter_strategy"] == LetterStrategy.TEMPLATE


def test_apply_default_strategy_with_llm(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    captured = {}
    def fake_apply(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openhunt.browser.actions.apply.apply_to_vacancies", fake_apply)

    runner.invoke(main, ["resume", "set", "abc123"])
    runner.invoke(main, [
        "llm", "setup",
        "--provider", "openrouter",
        "--api-key", "sk-test",
        "--model", "gpt-4",
    ])
    runner.invoke(main, ["apply", "--query", "python"])

    from openhunt.browser.actions.apply import LetterStrategy
    assert captured["letter_strategy"] == LetterStrategy.LLM


def test_apply_letter_flag_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    captured = {}
    def fake_apply(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openhunt.browser.actions.apply.apply_to_vacancies", fake_apply)

    runner.invoke(main, ["resume", "set", "abc123"])
    runner.invoke(main, [
        "llm", "setup",
        "--provider", "openrouter",
        "--api-key", "sk-test",
        "--model", "gpt-4",
    ])
    runner.invoke(main, ["apply", "--query", "python", "--letter", "template"])

    from openhunt.browser.actions.apply import LetterStrategy
    assert captured["letter_strategy"] == LetterStrategy.TEMPLATE


def test_apply_letter_flag_auto(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    captured = {}
    def fake_apply(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openhunt.browser.actions.apply.apply_to_vacancies", fake_apply)

    runner.invoke(main, ["resume", "set", "abc123"])
    runner.invoke(main, ["apply", "--query", "python", "--letter", "auto"])

    from openhunt.browser.actions.apply import LetterStrategy
    assert captured["letter_strategy"] == LetterStrategy.AUTO


def test_apply_uses_saved_strategy(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    captured = {}
    def fake_apply(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openhunt.browser.actions.apply.apply_to_vacancies", fake_apply)

    runner.invoke(main, ["resume", "set", "abc123"])
    runner.invoke(main, ["letter", "strategy", "auto"])
    runner.invoke(main, ["apply", "--query", "python"])

    from openhunt.browser.actions.apply import LetterStrategy
    assert captured["letter_strategy"] == LetterStrategy.AUTO


def test_apply_cli_overrides_saved_strategy(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    captured = {}
    def fake_apply(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openhunt.browser.actions.apply.apply_to_vacancies", fake_apply)

    runner.invoke(main, ["resume", "set", "abc123"])
    runner.invoke(main, ["letter", "strategy", "auto"])
    runner.invoke(main, ["apply", "--query", "python", "--letter", "off"])

    from openhunt.browser.actions.apply import LetterStrategy
    assert captured["letter_strategy"] == LetterStrategy.OFF


def test_letter_strategy_show_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["letter", "strategy"])
    assert result.exit_code == 0
    assert "не задана" in result.output


def test_letter_strategy_set_and_show(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["letter", "strategy", "auto"])
    assert result.exit_code == 0
    assert "auto" in result.output

    result = runner.invoke(main, ["letter", "strategy"])
    assert "auto" in result.output


def test_letter_strategy_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["letter", "strategy", "invalid"])
    assert result.exit_code != 0


def test_query_list_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["query", "list"])
    assert result.exit_code == 0
    assert "Нет сохранённых запросов" in result.output
