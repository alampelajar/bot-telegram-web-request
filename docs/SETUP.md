# Local setup (Windows / PowerShell)

Prerequisites:
- Python 3.11
- Git
- Docker Desktop (if using PostgreSQL through Compose)
- Telegram bot token from BotFather

## 1. Clone and enter the development branch

```powershell
git clone https://github.com/alampelajar/bot-telegram-web-request.git
cd bot-telegram-web-request
git checkout feat/automatic-web-controller-mvp
```

## 2. Create virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Configure local settings

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `BOT_TOKEN` in your local .env. Never paste the token into chat or commit this file.

## 4. Run the initial bot scaffold

```powershell
python -m app.main
```

Use `/start` in Telegram to view the menu. Account connection and Augestel operations are deliberately guarded placeholders until the permitted authentication method and integration contract are verified.

## Docker notes

Before deployment, set a strong `POSTGRES_PASSWORD` environment variable. Change the default development database password and apply migrations when database models are introduced. No production secrets should be placed directly in compose.yaml.
