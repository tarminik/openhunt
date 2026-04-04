# Tech Stack

## Language & Runtime

- **Python 3.12+**
- **uv** — package manager, virtual environments, tool distribution

## Distribution

- **PyPI package**: `openhunt-cli` — https://pypi.org/project/openhunt-cli/
- **Install**: `uv tool install openhunt-cli` or `pip install openhunt-cli`
- **Build**: `uv build`
- **Publish**: `uv publish` (uses PyPI token from `~/.pypirc` or `UV_PUBLISH_TOKEN`)

### Release checklist

1. Bump version in `pyproject.toml` AND `src/openhunt/__init__.py` (both must match)
2. Commit and push
3. `uv build`
4. `uv publish`

## Core Dependencies

| Library | Purpose |
|---------|---------|
| **Playwright** | Browser automation (the only way to interact with hh.ru — API closed for job seekers) |
| **Textual** | TUI framework for terminal interface |
| **Click** | CLI argument parsing and commands |
| **OpenAI** | LLM cover letter generation (OpenRouter / custom OpenAI-compatible providers) |

## Playwright

hh.ru API is no longer available for job seekers. All interaction goes through the browser via Playwright.

- Handles modern SPAs (hh.ru is React-based)
- Built-in auto-wait, network interception
- Headed mode for login (user solves CAPTCHA), headless for all other work
- Persistent browser context — reuse logged-in sessions across runs
- Debugging tools (trace viewer, codegen)

### Anti-bot considerations
- Persistent browser context (real browser profile, not fresh each time)
- Human-like delays between actions (randomized)
- All hh.ru selectors isolated in one place — they will break on site updates

## Textual

- CSS-based styling
- Widget system (tables, trees, inputs, modals)
- Async-first architecture (fits well with Playwright)
- Hot reload during development
