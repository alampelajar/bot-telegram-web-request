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

Augestel documents Bearer authentication using `Authorization: Bearer YOUR_API_KEY`, with API v1 Base URL `https://augestel.com/api/v1/iprn`. Both the API Base URL and API-key configuration are now present in the application and `.env.example`.

The integration remains disabled by default. The read-only client foundation is tested with mocked HTTP responses, but it has not yet called Augestel's live API because the exact documented resource endpoints and response schemas have not been provided. The `/addnumber` command validates a local draft only. Add Number submission, export download, and Return All are still unimplemented and do not send requests.

## Local quick start

1. Copy `.env.example` to `.env`.
2. Set `BOT_TOKEN` and your **regenerated** `AUGESTEL_API_KEY` in `.env`.
3. Keep `AUGESTEL_INTEGRATION_ENABLED=false` until endpoint docs are verified.
4. Install with `python -m pip install -e .`.
5. Run `python -m app.main`.
6. Send `/start` to the bot.

To validate an Add Number draft, use:

```text
/addnumber <termination_id> <termination_term_id> <count> <sort_type>
```

This validates the syntax and saves an operation-history record. It does **not** send a request.

Never commit `.env`, API keys, session cookies, credentials, HAR files, or exported account data. The API key visible in the earlier screenshot should be regenerated before use.
