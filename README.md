# Automatic Web Controller

Telegram bot for managing an authorized Augestel account.

## MVP scope

- Telegram user registration and per-user account connection state
- Add Number workflow (integration adapter is guarded)
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

The Telegram bot menu and persistent user/account status are implemented. Actual Augestel authentication is not enabled: the observed browser routes are not proof of a supported public API. The integration remains disabled until the permitted authentication method and request contract are confirmed.

## Local quick start

1. Copy `.env.example` to `.env`.
2. Set `BOT_TOKEN` in `.env`.
3. Install with `python -m pip install -e .`.
4. Run `python -m app.main`.
5. Send `/start` to the bot.

Local development defaults to SQLite and creates `data/automatic_web_controller.db` automatically. For Docker, set a strong `POSTGRES_PASSWORD` in `.env` and run `docker compose up --build`.

Never commit `.env`, session cookies, API tokens, credentials, HAR files, or exported account data.
