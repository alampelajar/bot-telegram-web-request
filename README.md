# Automatic Web Controller

Telegram bot for managing an authorized Augestel account.

## MVP scope

- Telegram user registration and per-user account connection state
- Add Number input validation and local draft preparation (no external request yet)
- Bearer-token API client foundation for read-only JSON GET requests
- Download Augestel export (feature adapter remains guarded)
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

Augestel's API documentation states that requests use `Authorization: Bearer YOUR_API_KEY`. The application now supports a secret API-key setting and a guarded, read-only JSON GET client. Set `AUGESTEL_API_BASE_URL` to the exact Base URL shown in Augestel API documentation; it is deliberately blank by default rather than guessed.

The integration remains disabled by default. No actual API endpoint has yet been called because the documented Base URL and endpoint paths have not been confirmed. The `/addnumber` command validates a local draft only. Add Number submission, export download, and Return All are still unimplemented and do not send requests.

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

This validates the syntax and saves an operation-history record. It does **not** send a request.

For API access, store the regenerated Augestel API key only in local `.env` or a deployment secret manager. Never commit `.env`, API keys, session cookies, credentials, HAR files, or exported account data. The API key visible in the earlier screenshot should be regenerated before use.
