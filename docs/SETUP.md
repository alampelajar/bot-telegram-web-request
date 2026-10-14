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

Set `BOT_TOKEN` in `.env`. Local development uses SQLite by default, so you do not need to start PostgreSQL separately. If you already have an older `.env`, update `DATABASE_URL` to:

```text
DATABASE_URL=sqlite+aiosqlite:///./data/automatic_web_controller.db
```

Never paste the bot token into chat or commit the `.env` file.

## 4. Run the bot

```powershell
python -m app.main
```

Use `/start` in Telegram. The database schema is initialized for local development and Telegram user/account status is persisted.

## Docker / PostgreSQL

Set a strong `POSTGRES_PASSWORD` in `.env`, then run:

```powershell
docker compose up --build
```

Compose overrides the local SQLite URL and connects the bot to PostgreSQL. Change the example password before using a remotely accessible deployment.

## Augestel connection status

The bot can persist a per-user connection status, but does not request passwords, cookies, or browser session tokens in Telegram. Actual Augestel login stays disabled until a supported authentication method and integration contract are verified.
