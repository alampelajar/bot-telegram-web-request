# Automatic Web Controller

Telegram bot for managing an authorized Augestel account.

## MVP scope

- Connect and inspect account connection state
- Add Number workflow (integration adapter is initially guarded)
- Download Augestel XLSX export
- Return All workflow with explicit confirmation and safety checks
- Operation history and user access controls

## Stack

- Python 3.11
- aiogram 3
- httpx
- SQLAlchemy 2 + PostgreSQL + Alembic
- pytest

## Status

Project scaffold. Augestel's observed web endpoints are not assumed to be a supported public API. Validate the permitted authentication and integration method before enabling operations that modify account state.

## Quick start

1. Copy `.env.example` to `.env` and configure values.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Run locally: `python -m app.main`

Never commit `.env`, session cookies, API tokens, credentials, or HAR files.
