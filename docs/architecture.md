# Architecture

## Project Structure

```
openhunt/
├── src/openhunt/
│   ├── __init__.py        # package metadata
│   ├── __main__.py        # python -m openhunt entry point
│   └── cli.py             # CLI commands (Click)
├── docs/                  # documentation
├── pyproject.toml         # project config
└── README.md
```

## Planned Modules

```
src/openhunt/
├── cli.py                 # CLI entry point and commands
├── tui/                   # Textual TUI application
│   ├── app.py             # main TUI app
│   └── screens/           # TUI screens
├── browser/               # Playwright automation
│   ├── session.py         # browser session management
│   ├── auth.py            # hh.ru authentication
│   └── actions/           # automated actions (apply, chat, etc.)
├── llm/                   # LLM integration
│   ├── client.py          # LLM client abstraction
│   └── prompts/           # prompt templates
└── config/                # user configuration
    └── settings.py        # config management
```

## Design Principles

1. **Modular** — each concern in its own module, easy to extend
2. **Async-first** — Playwright and Textual are both async, leverage that
3. **Offline-safe** — graceful handling of network issues
4. **User in control** — automation assists, human decides
