from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

router = Router()


async def _show_connect_info(message: Message) -> None:
    await message.answer(
        "Koneksi Augestel belum dikonfigurasi.\n\n"
        "Untuk keamanan, jangan kirim password, cookie, atau token sesi melalui chat. "
        "Metode autentikasi resmi harus dikonfirmasi sebelum koneksi akun diaktifkan."
    )


@router.message(Command("connect"))
async def connect_command(message: Message) -> None:
    await _show_connect_info(message)


@router.message(Command("account"))
async def account_command(message: Message) -> None:
    await message.answer(
        "<b>Status Akun</b>\nAugestel: <code>NOT_CONNECTED</code>\n"
        "Integrasi produksi belum diaktifkan."
    )


@router.callback_query(lambda query: query.data == "menu:connect")
async def connect_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await _show_connect_info(query.message)


@router.callback_query(lambda query: query.data == "menu:account")
async def account_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await query.message.answer(
            "Status akun: <code>NOT_CONNECTED</code>. Integrasi belum diaktifkan."
        )
