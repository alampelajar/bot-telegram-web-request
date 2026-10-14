# Automatic Web Controller

Telegram bot for managing an authorized Augestel account.

## MVP scope

- Telegram user registration and per-user account connection state
- Read-only My Numbers API integration with page navigation
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

Augestel documents Bearer authentication using `Authorization: Bearer YOUR_API_KEY`, with API v1 Base URL `https://augestel.com/api/v1/iprn`. The documented read-only `GET /numbers` endpoint is now integrated in the bot. It supports `page`, `per_page` (1–100), and optional `range_name`, and the bot renders number/range/rate/portal limit and pagination.

The integration remains disabled by default. After adding a **regenerated** key to local `.env`, verify the configuration and set `AUGESTEL_INTEGRATION_ENABLED=true` to enable the documented read-only endpoint. The API call is covered by mocked tests; no live request has been made from this development process.

The `/addnumber` command validates a local draft only. Add Number submission, export download, and Return All are still unimplemented and do not send requests.

## Local quick start

1. Copy `.env.example` to `.env`.
2. Set `BOT_TOKEN` and your **regenerated** `AUGESTEL_API_KEY` in `.env`.
3. After you are ready to allow the documented read-only API, set `AUGESTEL_INTEGRATION_ENABLED=true`.
4. Install with `python -m pip install -e .`.
5. Run `python -m app.main`.
6. Send `/start` to the bot. Use **📱 My Numbers** or `/numbers`; `/numbers 2` opens page 2.

To validate an Add Number draft, use:

```text
/addnumber <termination_id> <termination_term_id> <count> <sort_type>
```

This validates the syntax and saves an operation-history record. It does **not** send a request.

Never commit `.env`, API keys, session cookies, credentials, HAR files, or exported account data. The API key visible in the earlier screenshot should be regenerated before use.
