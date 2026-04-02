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
│   ├── session.py         # browser session management & persistence
│   ├── auth.py            # hh.ru authentication (interactive)
│   ├── selectors.py       # all hh.ru CSS/XPath selectors in one place
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

## Browser Session Management

All hh.ru interaction goes through Playwright. The hh.ru API is not available for job seekers.

### Browser Modes

- **Headed** — only for login. The user sees the browser, enters phone/SMS, solves CAPTCHA manually
- **Headless** — all subsequent work. The user interacts exclusively through the terminal (TUI/CLI)

### Authentication Flow

hh.ru requires phone number + SMS code for login, and often shows a CAPTCHA on the login page.

1. `openhunt login` opens a **headed** browser window on the hh.ru login page
2. The user enters their phone number, solves the CAPTCHA, enters the SMS code
3. Once logged in, openhunt saves the browser session to disk
4. All further commands run in **headless** mode using the saved session
5. If the session expires (detected by redirect to login page), openhunt asks the user to run `openhunt login` again

### Session Persistence

Playwright's persistent browser context (`browser_type.launch_persistent_context()`) stores session data to disk:

```
~/.openhunt/
├── browser/           # Playwright persistent context (cookies, localStorage, etc.)
└── config.toml        # user settings
```

Key points:
- Use `launch_persistent_context()` — this persists cookies, localStorage, sessionStorage automatically
- The browser profile directory survives between runs
- On session expiry, detect by checking for login page redirect or auth-related elements
- Re-auth is interactive: open headed browser, let user log in, save session again

### Anti-Bot Measures

- Persistent browser context (real browser profile, not a fresh one each time)
- Human-like randomized delays between actions
- Realistic viewport size, user-agent, locale settings

### Selector Isolation

All hh.ru selectors (CSS, XPath, text) are centralized in `browser/selectors.py`. When hh.ru updates their markup, only this file needs to change.
