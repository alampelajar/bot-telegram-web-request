from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.bot.keyboards import main_menu

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
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
        "/start — menu utama\n/connect — hubungkan akun\n/account — status akun\n"
        "/addnumber — tambah nomor\n/download — unduh ekspor XLSX\n"
        "/returnall — kembalikan semua nomor\n/history — riwayat operasi\n"
        "/cancel — batalkan alur yang belum dikonfirmasi"
    )
