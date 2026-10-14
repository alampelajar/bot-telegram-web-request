# Automatic Web Controller

Telegram bot for managing each user's own Augestel account.

## MVP scope

- Per-user Augestel API-key connection through a private Telegram chat
- Validate API keys against the documented read-only `GET /numbers` endpoint
- Encrypt user API keys at rest and keep them out of operation history
- Read-only My Numbers with pagination
- Add Number confirmation flow using fields observed in the website request
- Return All preview, fresh-count recheck, explicit confirmation, and safe unknown-outcome handling
- Export download remains guarded until its response contract is verified
- Per-user operation history and account disconnect

## Stack

- Python 3.11
- aiogram 3 with FSM for connect and write confirmation flows
- httpx
- SQLAlchemy 2
- SQLite for local development, PostgreSQL for Docker deployment
- Fernet encryption using `API_KEY_ENCRYPTION_KEY`
- pytest

## Configuration

The documented API v1 Base URL is `https://augestel.com/api/v1/iprn` and documented API requests use `Authorization: Bearer YOUR_API_KEY`.

1. Copy `.env.example` to `.env`.
2. Set `BOT_TOKEN`.
3. Generate a Fernet encryption key and set it in `API_KEY_ENCRYPTION_KEY`:
   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
4. Set `AUGESTEL_INTEGRATION_ENABLED=true` to allow the per-user API-key connection and documented read-only API.
5. Keep `AUGESTEL_API_BASE_URL=https://augestel.com/api/v1/iprn`.

**Back up `API_KEY_ENCRYPTION_KEY` securely.** If lost or changed, stored user API keys cannot be decrypted. Never commit `.env` or put the encryption key in the repository.

### Custom write routes

Augestel's published API documentation supplied so far describes read-only endpoints. The HAR showed website routes for Add Number and Return All, so the bot has a separate adapter for those observed paths. These are **not documented public API v1 endpoints**, and their acceptance of a Bearer API key has not been confirmed.

Custom writes are disabled by default. Only in a test environment, and only after checking with Augestel that your API key is permitted on these routes, an operator can opt in using:

```dotenv
AUGESTEL_CUSTOM_WRITE_ENABLED=true
```

The adapter sends the user's Bearer key to the same Augestel HTTPS host, follows no redirects, and does not fabricate, scrape, or replay browser cookies/CSRF/request tokens. If Augestel requires a browser session or anti-CSRF values, the operation will fail safely; do not try to bypass those controls. A redirect or timeout after POST is treated as an unknown outcome—check `/numbers` and the portal before trying again.

## Connect in Telegram

1. Open a **private chat** with the bot.
2. Send `/connect`.
3. Follow the prompt and send the Augestel API key by itself.
4. The bot validates it against `GET /numbers`, attempts to delete the submitted message, and stores encrypted key material linked to that Telegram user.
5. Use `/numbers` or **📱 My Numbers**. `/account` shows status; `/disconnect` removes the saved key.

The bot never echoes the key or writes it to operation history. Message deletion is best-effort, not guaranteed. Never share the key with people, groups, screenshots, this chat, or public repositories. If exposed, regenerate it in Augestel and reconnect.

## Add Number

Use the business fields observed in the website request:

```text
/addnumber <termination_id> <termination_term_id> <count> <sort_type>
```

The bot validates them and presents a confirmation button. Example IDs are illustrative only; use real values from the account. Confirm only once. If the result is unknown, check `/numbers` before attempting another add.

## Return All

Use the **↩️ Return All** menu or `/returnall`. The bot reads the current total, shows it, and asks for confirmation. If the number count changes before confirmation, it asks you to review the new count. This action can return all assigned numbers. If the result is uncertain, do not retry until checking the account.

## Current limitations

Add Number and Return All use observed website routes guarded by `AUGESTEL_CUSTOM_WRITE_ENABLED`; they have not been verified against the live account in this development process. These routes might reject Bearer auth or require browser-specific CSRF/session behavior, which the bot does not bypass. Export download, Earnings, and Message History still need their exact documented response contracts before implementation.

## Run locally

```powershell
python -m pip install -e .
python -m app.main
```

Never commit API keys, the encryption key, `.env`, session cookies, credentials, HAR files, or exported account data.
