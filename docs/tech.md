# Tech Stack

## Language & Runtime

- **Python 3.12+**
- **uv** — package manager, virtual environments, tool distribution

## Core Dependencies

| Library | Purpose |
|---------|---------|
| **Playwright** | Browser automation (the only way to interact with hh.ru — API closed for job seekers) |
| **Textual** | TUI framework for terminal interface |
| **Click** | CLI argument parsing and commands |

## Planned Dependencies

| Library | Purpose |
|---------|---------|
| LLM SDK (TBD) | Cover letter generation, chat automation |

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
