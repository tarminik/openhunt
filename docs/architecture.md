# Architecture

## Project Structure (current)

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
├── browser/               # Playwright automation
│   ├── session.py         # browser session management & persistence
│   ├── auth.py            # hh.ru authentication (interactive, headed)
│   ├── selectors.py       # all hh.ru CSS/XPath selectors in one place
│   └── actions/           # automated actions
│       ├── apply.py       # apply to vacancies
│       ├── search.py      # search and list vacancies
│       └── resume.py      # resume actions (raise, etc.)
├── llm/                   # LLM integration (Phase 3)
│   ├── client.py          # LLM client abstraction
│   └── prompts/           # prompt templates
├── memory/                # memory system (Phase 3)
│   ├── store.py           # read/write memory storage
│   └── match.py           # similarity matching via LLM
├── tui/                   # Textual TUI application (Phase 4)
│   ├── app.py             # main TUI app
│   └── screens/           # TUI screens
└── config/                # user configuration
    └── settings.py        # config management
```

## Data Directory

```
~/.openhunt/
├── browser/               # Playwright persistent context (cookies, localStorage)
├── memory/                # learned answers, chat patterns, user-provided data
└── config.toml            # user settings
```

## Design Principles

1. **Modular** — each concern in its own module, easy to extend
2. **Async-first** — Playwright and Textual are both async, leverage that
3. **Offline-safe** — graceful handling of network issues
4. **User in control** — automation assists, human decides
5. **Progressive autonomy** — starts manual, learns from user, becomes autonomous over time

## Browser Session Management

All hh.ru interaction goes through Playwright. The hh.ru API is not available for job seekers.

### Browser Modes

- **Headed** — only for login. The user sees the browser, enters phone/SMS, solves CAPTCHA manually
- **Headless** — all other operations. The user interacts exclusively through the terminal (TUI/CLI)

### Authentication Flow

hh.ru requires phone number + SMS code for login, and often shows a CAPTCHA on the login page.

1. `openhunt login` opens a **headed** browser window on the hh.ru login page
2. The user enters their phone number, solves the CAPTCHA, enters the SMS code
3. Once logged in, openhunt saves the browser session to disk
4. All further commands run in **headless** mode using the saved session
5. If the session expires (detected by redirect to login page), openhunt asks the user to run `openhunt login` again

### Session Persistence

Playwright's persistent browser context (`browser_type.launch_persistent_context()`) stores session data to disk in `~/.openhunt/browser/`.

Key points:
- `launch_persistent_context()` persists cookies, localStorage, sessionStorage automatically
- The browser profile directory survives between runs
- On session expiry, detect by checking for login page redirect or auth-related elements
- Re-auth is interactive: open headed browser, let user log in, save session again

### Anti-Bot Measures

- Persistent browser context (real browser profile, not a fresh one each time)
- Human-like randomized delays between actions
- Realistic viewport size, user-agent, locale settings

### Selector Isolation

All hh.ru selectors (CSS, XPath, text) are centralized in `browser/selectors.py`. When hh.ru updates their markup, only this file needs to change.

## Vacancy Search & Filtering

hh.ru has a powerful built-in query language. openhunt passes the user's query string directly to hh.ru search — no custom filtering needed on our side.

### hh.ru Query Language

Supports boolean operators, field-specific search, exact matching, and more:

| Syntax | Meaning | Example |
|--------|---------|---------|
| `AND` (or space) | All words required | `python AND django` |
| `OR` | Any of the words | `backend OR бекенд` |
| `NOT` | Exclude | `python NOT стажёр` |
| `!word` | Exact word (no synonyms) | `!python` |
| `"phrase"` | Exact phrase | `"senior developer"` |
| `NAME:` | Search in vacancy title | `NAME:python` |
| `COMPANY_NAME:` | Search in company name | `COMPANY_NAME:Яндекс` |
| `DESCRIPTION:` | Search in description | `DESCRIPTION:fastapi` |
| `^NAME:` | Title exactly equals | `^NAME:программист` |
| `(...)` | Grouping | `(python OR golang) AND NOT junior` |

Full reference: https://hh.ru/article/25295

### Search Modes in Phase 1

- **By query** — user provides a query string, openhunt passes it to hh.ru search as-is
- **By saved query** — user runs a previously saved named query
- **Recommended** — vacancies from the "Для вас" page (hh.ru recommends based on resume and history)

No custom filtering logic on our side — hh.ru's query language is powerful enough. LLM-based relevance scoring on top of search results is planned for Phase 3+.

### Saved Queries

Users can save complex queries under a name and reuse them without retyping:

```bash
# Save a query
openhunt query save backend "NAME:(python OR golang) AND NOT стажёр"

# List saved queries
openhunt query list

# Delete a saved query
openhunt query delete backend

# Apply using a saved query
openhunt apply --saved backend
```

Stored in `~/.openhunt/config.toml`:

```toml
[queries]
backend = "NAME:(python OR golang) AND NOT стажёр"
ai = "NAME:(ml OR ai OR machine learning) AND python"
```

## Phase 1 Scope

What we build first (no LLM):

1. **`openhunt login`** — interactive headed login, session persistence
2. **`openhunt apply`** — auto-apply to vacancies that have no required cover letter or questionnaire
   - `--query "..."` — search by inline query
   - `--saved <name>` — search by saved query
   - `--recommended` — apply from the recommended vacancies page
   - `--resume <id>` — hh.ru resume ID to apply with (required)
   - `--limit N` — maximum number of applications per run
   - Paginate through search results until `--limit` is reached
   - Skip (do not count toward limit):
     - Vacancies already applied to
     - Vacancies that require a cover letter
     - Vacancies that require a questionnaire
   - Report results: how many applied, how many skipped (and why)
3. **`openhunt query`** — manage saved queries (save, list, delete)

The architecture is designed so that LLM, memory, and TUI modules can be added later without refactoring the browser layer.
