from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import confirm_return_all

router = Router()


async def _not_enabled(message: Message, feature: str) -> None:
    await message.answer(
        f"<b>{feature}</b> belum dieksekusi.\n"
        "Integrasi Augestel masih dalam mode aman karena metode autentikasi dan izin "
        "endpoint perlu divalidasi terlebih dahulu."
    )


@router.message(Command("addnumber"))
async def add_number_command(message: Message) -> None:
    await _not_enabled(message, "Add Number")


@router.message(Command("download"))
async def download_command(message: Message) -> None:
    await _not_enabled(message, "Download Numbers")


@router.message(Command("returnall"))
async def return_all_command(message: Message) -> None:
    await message.answer(
        "<b>⚠️ Return All</b>\n\n"
        "Tindakan ini dapat mengembalikan seluruh nomor pada akun Augestel yang terhubung.\n"
        "Saat ini integrasi belum diaktifkan, jadi tombol konfirmasi tidak akan mengirim request.",
        reply_markup=confirm_return_all(),
    )


@router.message(Command("history"))
async def history_command(message: Message) -> None:
    await message.answer("Riwayat operasi belum tersedia karena database belum dimigrasikan.")


@router.message(Command("cancel"))
async def cancel_command(message: Message) -> None:
    await message.answer("Tidak ada operasi aktif yang dieksekusi.")


@router.callback_query(lambda query: query.data == "menu:add")
async def add_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await _not_enabled(query.message, "Add Number")


@router.callback_query(lambda query: query.data == "menu:download")
async def download_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await _not_enabled(query.message, "Download Numbers")


@router.callback_query(lambda query: query.data == "menu:return_all")
async def return_all_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await query.message.answer(
            "<b>⚠️ Return All</b>\n\n"
            "Tindakan ini dapat mengembalikan seluruh nomor. Integrasi masih dinonaktifkan; "
            "konfirmasi tidak akan menjalankan request.",
            reply_markup=confirm_return_all(),
        )


@router.callback_query(lambda query: query.data == "return_all:confirm")
async def confirm_return_all_callback(query: CallbackQuery) -> None:
    await query.answer("Integrasi belum diaktifkan.", show_alert=True)
    if query.message:
        await query.message.answer(
            "Operasi tidak dijalankan. Integrasi Augestel masih dinonaktifkan."
        )


@router.callback_query(lambda query: query.data == "return_all:cancel")
async def cancel_return_all_callback(query: CallbackQuery) -> None:
    await query.answer("Dibatalkan.")
    if query.message:
        await query.message.answer("Return All dibatalkan. Tidak ada request yang dikirim.")


@router.callback_query(lambda query: query.data == "menu:history")
async def history_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await query.message.answer("Riwayat operasi belum tersedia.")
