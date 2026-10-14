# Automatic Web Controller

Telegram bot for managing each user's own Augestel account through the documented API.

## MVP scope

- Per-user Augestel API-key connection through a private Telegram chat
- Verify API keys against read-only `GET /numbers` before storing
- Encrypt user API keys at rest; do not place them in operation history
- Read-only My Numbers with pagination
- Add Number input validation and local draft preparation (no external request yet)
- Download Augestel export and Return All remain guarded placeholders
- Per-user operation history and account disconnect

## Stack

- Python 3.11
- aiogram 3 with FSM for the connect flow
- httpx
- SQLAlchemy 2
- SQLite for simple local development, PostgreSQL for Docker deployment
- Fernet encryption using `API_KEY_ENCRYPTION_KEY`
- pytest

## Configuration

Augestel's documented API v1 Base URL is `https://augestel.com/api/v1/iprn` and it uses `Authorization: Bearer YOUR_API_KEY`.

1. Copy `.env.example` to `.env`.
2. Set `BOT_TOKEN`.
3. Generate an encryption key and set it in `API_KEY_ENCRYPTION_KEY`:
   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
4. Set `AUGESTEL_INTEGRATION_ENABLED=true` when the operator is ready to allow the documented read-only API.
5. Keep `AUGESTEL_API_BASE_URL=https://augestel.com/api/v1/iprn`.

**Back up `API_KEY_ENCRYPTION_KEY` securely.** If it is lost or changed, previously stored API keys cannot be decrypted. Never commit `.env` or put the encryption key in the repo.

## Connect in Telegram

1. Open a **private chat** with the bot.
2. Send `/connect`.
3. Follow the prompt and send the Augestel API key by itself.
4. The bot validates the key with the read-only My Numbers endpoint, tries to delete the submitted message, and stores only encrypted key material linked to your Telegram account.
5. Use `/numbers` or the **📱 My Numbers** menu. `/numbers 2` opens page 2. Use `/account` to see connection status, or `/disconnect` to remove your saved key.

The bot never echoes the key or writes it to operation history. Message deletion is best-effort, not guaranteed. Send the key only to your private bot chat for the connection flow. Never share it with other people, groups, screenshots, this chat, or public repositories. If exposed, regenerate it in Augestel and reconnect.

## Current limitations

The API docs provided so far document read-only numbers, earnings, and message history. Add Number, export download, and Return All do not yet have documented API endpoints and remain disabled; local Add Number draft validation does not send any request. The older `/Switchfy/...` website routes observed in browser HAR files are not automatically treated as public API endpoints.

## Run locally

```powershell
python -m pip install -e .
python -m app.main
```

Never commit API keys, the encryption key, `.env`, session cookies, credentials, HAR files, or exported account data.
