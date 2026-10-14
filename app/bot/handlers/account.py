import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.services.accounts import (
    disconnect_account,
    get_account_status,
    register_or_touch_user,
    set_connection_pending,
)
from app.services.operation_history import record_operation

router = Router()
logger = logging.getLogger(__name__)


def _status_label(status: str) -> str:
    return {
        "not_registered": "Belum terdaftar",
        "not_connected": "Belum terhubung",
        "disconnected": "Terputus",
        "auth_method_required": "Menunggu metode autentikasi",
        "connected": "Terhubung",
        "auth_failed": "Autentikasi gagal",
        "session_expired": "Sesi kedaluwarsa",
    }.get(status, status.replace("_", " ").capitalize())


async def _connect_account(message: Message) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Identitas Telegram tidak tersedia.")
        return
    try:
        user_id = await register_or_touch_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )
        status = await set_connection_pending(user_id)
        await record_operation(
            user.id,
            "connect_account",
            status.connection_status,
            result_summary="Connection request recorded; actual Augestel authentication has not run.",
        )
    except Exception:
        logger.exception("Could not initialize account connection")
        await message.answer(
            "Tidak dapat menyiapkan koneksi akun karena database bermasalah. "
            "Periksa database dan coba lagi."
        )
        return

    await message.answer(
        "<b>Connect Augestel</b>\n\n"
        "Permintaan koneksi sudah dicatat. Status: "
        f"<code>{_status_label(status.connection_status)}</code>.\n\n"
        "Bot belum login ke Augestel. Metode autentikasi yang diizinkan untuk integrasi "
        "belum dikonfirmasi. Jangan kirim password, cookie, atau token sesi melalui chat. "
        "Koneksi hanya akan diaktifkan setelah metode autentikasi resmi tersedia."
    )


async def _show_account_status(message: Message) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Identitas Telegram tidak tersedia.")
        return
    try:
        status = await get_account_status(user.id)
    except Exception:
        logger.exception("Could not load account status")
        await message.answer("Gagal membaca status akun. Periksa koneksi database.")
        return

    validated = (
        status.last_validated_at.strftime("%Y-%m-%d %H:%M UTC")
        if status.last_validated_at
        else "Belum pernah"
    )
    await message.answer(
        "<b>My Account</b>\n"
        f"Provider: <code>{status.provider}</code>\n"
        f"Status: <code>{_status_label(status.connection_status)}</code>\n"
        f"Validasi terakhir: <code>{validated}</code>"
    )


async def _disconnect_account(message: Message) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Identitas Telegram tidak tersedia.")
        return
    try:
        disconnected = await disconnect_account(user.id)
    except Exception:
        logger.exception("Could not disconnect account")
        await message.answer("Gagal memutuskan koneksi. Periksa koneksi database.")
        return
    if disconnected:
        try:
            await record_operation(
                user.id,
                "disconnect_account",
                "disconnected",
                result_summary="Connection state cleared for this Telegram user.",
            )
        except Exception:
            logger.exception("Could not record account disconnect event")
        await message.answer("Status koneksi Augestel sudah diubah menjadi disconnected.")
    else:
        await message.answer("Belum ada koneksi Augestel yang perlu diputuskan.")


@router.message(Command("connect"))
async def connect_command(message: Message) -> None:
    await _connect_account(message)


@router.message(Command("account"))
async def account_command(message: Message) -> None:
    await _show_account_status(message)


@router.message(Command("disconnect"))
async def disconnect_command(message: Message) -> None:
    await _disconnect_account(message)


@router.callback_query(lambda query: query.data == "menu:connect")
async def connect_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await _connect_account(query.message)


@router.callback_query(lambda query: query.data == "menu:account")
async def account_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await _show_account_status(query.message)
