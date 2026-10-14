# Local setup (Windows / PowerShell)

Prerequisites:
- Python 3.11
- Git
- A Telegram bot token from BotFather
- Docker Desktop only if you prefer PostgreSQL via Compose

## 1. Clone and enter the development branch

```powershell
git clone https://github.com/alampelajar/bot-telegram-web-request.git
cd bot-telegram-web-request
git checkout feat/automatic-web-controller-mvp
```

## 2. Create a virtual environment and install

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

## 3. Configure local settings

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `BOT_TOKEN` in `.env`. Local development uses SQLite by default, so you do not need to start PostgreSQL separately. The startup routine creates missing tables and adds compatibility columns to an older database without deleting existing data. If you already have an older `.env`, keep the local SQLite URL as:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./data/automatic_web_controller.db
```

Generate a Fernet encryption key:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put its output into `API_KEY_ENCRYPTION_KEY` in `.env`, then set:

```dotenv
AUGESTEL_API_BASE_URL=https://augestel.com/api/v1/iprn
AUGESTEL_INTEGRATION_ENABLED=true
AUGESTEL_CUSTOM_WRITE_ENABLED=false
```

Do not put a user's Augestel API key in the server's `.env`. Each Telegram user provides their own API key via the bot's private chat. Keep `API_KEY_ENCRYPTION_KEY` backed up and secret; changing or losing it makes stored API keys unrecoverable.

Never paste the bot token, any Augestel API key, or the encryption key into this chat or commit `.env`.

## 4. Run the bot

```powershell
python -m app.main
```

Use `/start` in Telegram.

## Connect an individual Augestel account

1. Open the bot's **private chat**, not a group.
2. Send `/connect`.
3. Send the Augestel API key as a single text message when prompted.
4. The bot validates the key with the documented read-only `GET /numbers` endpoint before storing it encrypted per Telegram user.
5. Use `/numbers` to read the user's assigned numbers, `/account` to check status, or `/disconnect` to remove the saved key.

The bot attempts to delete the submitted API-key message after receiving it, but deletion is best-effort. Never share the key with other users, groups, screenshots, this chat, or a public repository. If exposed, regenerate it in Augestel and reconnect.

## Docker / PostgreSQL

Set a strong `POSTGRES_PASSWORD` in `.env`, then run:

```powershell
docker compose up --build
```

Compose overrides the local SQLite URL and connects the bot to PostgreSQL. Change the example password before using a remotely accessible deployment.

## Feature status

My Numbers is implemented through the documented read-only API. Add Number and Return All have custom adapters for website routes observed in HAR; these are not documented public API v1 endpoints. They are disabled by default. Set `AUGESTEL_CUSTOM_WRITE_ENABLED=true` only in a test environment after confirming with Augestel that Bearer API-key auth is supported on those routes. The adapter fetches a fresh CSRF token from the live numbers page, and Add Number fetches a fresh `request_token` from termination metadata; it does not replay tokens from HAR or bypass challenges. If the page redirects to login, the adapter stops without sending the write. A redirect or timeout after POST means the write outcome could be unknown; check `/numbers` and the portal before retrying. Export download remains blocked pending its response contract.

## Add Number and Return All from Telegram

- `/addnumber <termination_id> <termination_term_id> <count> <sort_type>` expects numeric termination/term IDs and a `sort_type` matching the termination metadata. It validates the draft and presents a confirmation button before any POST.
- `/returnall` or the **Return All** menu first shows the currently reported number count, then asks for confirmation. If that count changes before confirmation, the bot asks for a fresh confirmation.
- Cancel buttons clear the pending operation. The bot does not retry a write operation automatically after an uncertain response.
