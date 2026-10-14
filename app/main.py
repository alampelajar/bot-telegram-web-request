import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot.handlers import router
from app.config import get_settings
from app.database.init_db import create_schema
from app.database.session import close_database
from app.logging_config import configure_logging


async def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    settings = get_settings()
    token = settings.bot_token.get_secret_value().strip()
    if not token:
        raise RuntimeError("BOT_TOKEN belum diatur. Salin .env.example menjadi .env.")

    await create_schema()
    logger.info("Database schema ready")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    logger.info("Automatic Web Controller starting")
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await bot.session.close()
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
