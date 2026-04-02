# Tech Stack

## Language & Runtime

- **Python 3.12+**
- **uv** — package manager, virtual environments, tool distribution

## Core Dependencies

| Library | Purpose |
|---------|---------|
| **Playwright** | Browser automation for hh.ru interactions |
| **Textual** | TUI framework for terminal interface |
| **Click** | CLI argument parsing and commands |

## Planned Dependencies

| Library | Purpose |
|---------|---------|
| LLM SDK (TBD) | Cover letter generation, chat automation |

## Why This Stack

### Python
- First-class Playwright support (official library)
- Richest LLM ecosystem (anthropic, openai, litellm)
- Textual — most capable TUI framework across any language
- Low barrier to entry for contributors

### uv
- Fast dependency resolution
- Built-in virtual environment management
- `uvx openhunt` for zero-install usage
- Replaces pip, pip-tools, virtualenv, pipx

### Playwright vs Selenium/requests
- Playwright handles modern SPAs (hh.ru is React-based)
- Built-in auto-wait, network interception
- Headless and headed modes
- Better debugging tools (trace viewer, codegen)

### Textual vs other TUI frameworks
- CSS-based styling
- Widget system (tables, trees, inputs, modals)
- Async-first architecture (fits well with Playwright)
- Hot reload during development
