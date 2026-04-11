# Repository Guidelines

## Project Structure & Module Organization
`main.py` wires the bot, scheduler, and dashboard. Core Python logic lives in `bot/` (`listener.py`, `pipeline.py`, `publisher.py`, `rewriter.py`, etc.). The FastAPI dashboard is in `dashboard/`, with route handlers in `routes.py` and Jinja templates in `dashboard/templates/`. Telegram and SQLite runtime state is stored under `data/`; treat that directory as generated state, not source. Static watermark assets live in `assets/`. The WhatsApp sender is a separate Node microservice in `whatsapp/`. Tests mirror the Python modules in `tests/`.

## Build, Test, and Development Commands
Set up Python with `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`. Install the WhatsApp service with `cd whatsapp && npm install`. Run the Node service with `node whatsapp/index.js`. Run the full app from the repo root with `PYTHONPATH=. python main.py`. Run the test suite with `pytest`. Useful helpers: `python scripts/list_groups.py` lists Telegram dialogs, and `python scripts/test_ali_api.py` sanity-checks AliExpress credentials.

## Coding Style & Naming Conventions
Follow the existing style: 4-space indentation, PEP 8 naming, type hints where practical, and small single-purpose modules. Use `snake_case` for Python files, functions, and variables; use `PascalCase` for dataclasses and other classes. Keep async boundaries explicit for Telegram, HTTP, and scheduler code. In `whatsapp/`, keep the current ESM style and `const`-first JavaScript patterns. No formatter or linter is configured here, so match surrounding code closely and keep imports tidy.

## Testing Guidelines
Tests use `pytest` with `pytest-asyncio`, `respx`, and in-memory SQLite fixtures from `tests/conftest.py`. Name new files `tests/test_<module>.py` and group async behavior under explicit test cases. Mock external services instead of calling Telegram, OpenAI, AliExpress, or WhatsApp directly. Add or update tests whenever pipeline logic, config loading, publishing rules, or dashboard behavior changes.

## Commit & Pull Request Guidelines
Recent history uses short conventional prefixes such as `feat:`, `fix:`, and `docs:`. Keep commit subjects imperative and scoped to one change. PRs should summarize behavior changes, mention config or secret impacts, and link related planning docs or issues when relevant. Include screenshots for `dashboard/templates/` changes and note any manual verification needed for Telegram or WhatsApp flows.

## Security & Configuration Tips
Never commit `.env`, session files, `data/*.db`, `data/bot.log`, or WhatsApp auth state. Keep secrets in `.env`, non-secret defaults in `config.yaml`, and update `.env.example` when adding required variables.
