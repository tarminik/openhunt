# openhunt

CLI tool for automating job seeker actions on hh.ru.

## Features (planned)

- Apply to vacancies automatically
- Generate cover letters with LLM
- Fill out application forms
- Chat with employers
- TUI interface

## Tech Stack

- **Python 3.12+** with **uv**
- **Playwright** for browser automation
- **Textual** for TUI
- **Click** for CLI

## Install

```bash
uv tool install openhunt
```

## Development

```bash
git clone https://github.com/tarminik/openhunt.git
cd openhunt
uv sync
uv run openhunt --help
```

## License

MIT
