# Automatic Web Controller

Telegram bot for managing an authorized Augestel account.

## MVP scope

- Telegram user registration and per-user account connection state
- Add Number input validation and local draft preparation (no external request yet)
- Download Augestel XLSX export (integration adapter is guarded)
- Return All workflow with explicit confirmation and safety checks
- Operation history and access-control foundations

## Stack

- Python 3.11
- aiogram 3
- httpx
- SQLAlchemy 2
- SQLite for simple local development, PostgreSQL for Docker deployment
- Alembic for future managed migrations
- pytest

## Status

The Telegram menu and persistent user/account status are implemented. The `/addnumber` command can validate a local draft from the observed business fields, but it does not execute an Augestel request. Actual authentication and all website operations remain disabled until an approved authentication method and request contract are confirmed. Observed website routes are not proof of a supported public API.

## Local quick start

1. Copy `.env.example` to `.env`.
2. Set `BOT_TOKEN` in `.env`.
3. Install with `python -m pip install -e .`.
4. Run `python -m app.main`.
5. Send `/start` to the bot.

To validate an Add Number draft, use:

```text
/addnumber <termination_id> <termination_term_id> <count> <sort_type>
```

This validates the syntax and saves an operation-history record. It does **not** send a request. Do not include passwords, cookies, CSRF tokens, or session tokens in the command.

Local development defaults to SQLite and creates `data/automatic_web_controller.db` automatically. For Docker, set a strong `POSTGRES_PASSWORD` in `.env` and run `docker compose up --build`.

Never commit `.env`, session cookies, API tokens, credentials, HAR files, or exported account data.
