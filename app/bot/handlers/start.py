import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.bot.keyboards import main_menu
from app.services.accounts import register_or_touch_user

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def start(message: Message) -> None:
    if message.from_user is not None:
        try:
            await register_or_touch_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
            )
        except Exception:
            logger.exception("Could not register Telegram user")
            await message.answer(
                "Database belum siap. Periksa koneksi database lalu jalankan ulang bot."
            )
            return

    await message.answer(
        "<b>Automatic Web Controller</b>\n\n"
        "Bot untuk mengelola akun Augestel yang kamu miliki.\n"
        "Hubungkan akun terlebih dahulu sebelum menjalankan operasi.\n\n"
        "Pilih fitur dari menu berikut:",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>Panduan</b>\n"
        "/start — menu utama\n/connect — mulai proses koneksi akun\n"
        "/account — status akun\n/disconnect — putuskan koneksi\n"
        "/addnumber — tambah nomor\n/download — unduh ekspor XLSX\n"
        "/returnall — kembalikan semua nomor\n/history — riwayat operasi\n"
        "/cancel — batalkan alur yang belum dikonfirmasi"
    )
