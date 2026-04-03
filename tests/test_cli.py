"""Tests for CLI argument validation."""

from click.testing import CliRunner

from openhunt.cli import main


runner = CliRunner()


def test_version():
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


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


def test_query_list_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")

    result = runner.invoke(main, ["query", "list"])
    assert result.exit_code == 0
    assert "Нет сохранённых запросов" in result.output
