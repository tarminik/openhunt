# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is openhunt

CLI-инструмент для автоматизации поиска работы на hh.ru. Автоматические отклики на вакансии, поднятие резюме, управление поисковыми запросами. Всё взаимодействие с hh.ru через Playwright (API закрыт для соискателей).

## Commands

```bash
uv sync                          # установить зависимости
playwright install chromium       # установить браузер
uv run openhunt --help           # запустить CLI
uv run openhunt login            # авторизация (headed браузер)
uv run openhunt apply --resume <id> --query "python" --limit 5
uv run openhunt resume raise     # поднять резюме

# Testing
uv run pytest -v                 # запустить все тесты
uv run pytest tests/test_config.py            # один файл
uv run pytest tests/test_cli.py::test_version # один тест
```

## Architecture

**Модули:**
- `cli.py` — Click-группы и команды (точка входа: `openhunt.cli:main`)
- `config.py` — TOML-конфигурация и пути (`~/.openhunt/`)
- `browser/session.py` — persistent Playwright context, `check_auth()`, `human_delay()`
- `browser/selectors.py` — все CSS-селекторы hh.ru в одном месте
- `browser/actions/` — каждая команда в своём файле (`apply.py`, `resume.py`)

**Browser modes:** headed только для `login` (пользователь вводит SMS/капчу), headless для всего остального.

**Ключевой паттерн — action-функция:**
1. Открыть `browser_context(headless=True)`
2. Проверить `check_auth(page)` — если сессия протухла, попросить `openhunt login`
3. Выполнить действия с `human_delay()` между шагами
4. Вывести результат через `click.echo()`

**Lazy imports в CLI:** команды в `cli.py` используют отложенный import внутри функции-обработчика (не на уровне модуля), чтобы не загружать Playwright при `--help`.

**Селекторы hh.ru** централизованы в `browser/selectors.py`. Все `data-qa` атрибуты в одном месте — при обновлении сайта менять только этот файл.

**Данные пользователя** хранятся в `~/.openhunt/`: `browser/` (persistent context Playwright), `config.toml` (сохранённые запросы).

**CI:** GitHub Actions запускает `uv run pytest -v` на push/PR в main.

## Key conventions

- Документация пользователя (README) на русском языке
- Внутренняя документация (docs/, код) на английском
- hh.ru использует `data-qa` атрибуты — искать их при добавлении новых селекторов
- Некоторые `data-qa` содержат несколько значений через пробел — использовать `[data-qa~='value']` вместо `[data-qa='value']`
- Некоторые элементы существуют в DOM, но hidden (мобильное меню) — использовать `query_selector` (проверка наличия), а не `wait_for_selector` (проверка видимости)
- hh.ru использует `\xa0` (non-breaking space) в текстах — учитывать при парсинге
- Коммиты без Co-Authored-By
- Планирование через GitHub Issues с лейблами `phase:N` и `priority:*`
- Высокоуровневое планирование в `docs/`
