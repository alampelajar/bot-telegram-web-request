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

My Numbers is implemented as a read-only API integration. Add Number, export download, and Return All remain blocked until their official API endpoints/contracts are available; a local Add Number draft does not execute a request.
