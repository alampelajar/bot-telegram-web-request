import logging
import re
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, User as TelegramUser
from pydantic import SecretStr

from app.config import get_settings
from app.integrations.augestel import (
    AugestelClient,
    AugestelIntegrationDisabled,
    AugestelIntegrationError,
)
from app.services.accounts import (
    disconnect_account,
    get_account_status,
    register_or_touch_user,
    save_api_key_for_user,
)
from app.services.operation_history import record_operation
from app.services.secret_store import SecretStorageError, encrypt_api_key

router = Router()
logger = logging.getLogger(__name__)


class ConnectApiKeyFlow(StatesGroup):
    waiting_for_api_key = State()


def _status_label(status: str) -> str:
    return {
        "not_registered": "Belum terdaftar",
        "not_connected": "Belum terhubung",
        "disconnected": "Terputus",
        "auth_method_required": "Menunggu API Key",
        "connected": "Terhubung",
        "auth_failed": "Autentikasi gagal",
        "session_expired": "Sesi kedaluwarsa",
    }.get(status, status.replace("_", " ").capitalize())


async def _start_api_key_flow(
    message: Message,
    telegram_user: TelegramUser | None,
    state: FSMContext,
) -> None:
    if telegram_user is None:
        await message.answer("Identitas Telegram tidak tersedia.")
        return
    if message.chat.type != ChatType.PRIVATE:
        await message.answer(
            "Demi keamanan, hubungkan Augestel melalui chat pribadi bot ini. "
            "Jangan kirim API Key ke grup."
        )
        return

    settings = get_settings()
    if not settings.augestel_integration_enabled:
        await state.clear()
        await message.answer(
            "Integrasi Augestel belum diaktifkan oleh pengelola bot. "
            "Coba lagi setelah konfigurasi server siap."
        )
        return
    try:
        # Fail before asking users for a secret if the at-rest encryption key is missing/invalid.
        encrypt_api_key("configuration-validation-only")
        await register_or_touch_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
        )
    except SecretStorageError:
        await state.clear()
        await message.answer(
            "Penyimpanan aman belum dikonfigurasi. Pengelola bot harus mengatur "
            "<code>API_KEY_ENCRYPTION_KEY</code>, lalu merestart bot."
        )
        return
    except Exception:
        logger.exception("Could not initialize user API-key connection flow")
        await message.answer("Gagal menyiapkan koneksi akun. Periksa database dan coba lagi.")
        return

    await state.set_state(ConnectApiKeyFlow.waiting_for_api_key)
    await message.answer(
        "<b>Hubungkan akun Augestel dengan API Key</b>\n\n"
        "1. Kirim API Key Augestel saja sebagai pesan teks di chat pribadi ini.\n"
        "2. Bot akan memvalidasi key ke endpoint baca resmi sebelum menyimpannya.\n"
        "3. Jika valid, key disimpan dalam bentuk terenkripsi dan tidak ditampilkan ulang.\n\n"
        "<b>⚠️ Jaga kerahasiaan API Key.</b> Jangan membagikannya ke orang lain, grup, "
        "screenshot, atau repositori publik. Jangan kirim ke chat ini selain untuk proses "
        "koneksi yang kamu mulai. Bot akan mencoba menghapus pesan yang berisi key setelah "
        "menerimanya, tetapi penghapusan pesan tidak bisa dijamin dalam semua kondisi.\n\n"
        "Kirim <code>/cancel</code> untuk membatalkan."
    )


@router.message(Command("connect"))
async def connect_command(message: Message, state: FSMContext) -> None:
    await _start_api_key_flow(message, message.from_user, state)


@router.callback_query(lambda query: query.data == "menu:connect")
async def connect_menu(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        await _start_api_key_flow(query.message, query.from_user, state)


@router.message(ConnectApiKeyFlow.waiting_for_api_key)
async def receive_api_key(message: Message, state: FSMContext) -> None:
    if message.chat.type != ChatType.PRIVATE:
        await state.clear()
        await message.answer("Proses koneksi dibatalkan. API Key hanya boleh dikirim di chat pribadi bot.")
        return

    incoming = message.text
    if incoming is None:
        await message.answer("Kirim API Key sebagai teks, atau ketik /cancel untuk membatalkan.")
        return

    stripped = incoming.strip()
    if stripped.lower() in {"/cancel", "cancel", "batal"}:
        await state.clear()
        await message.answer("Koneksi Augestel dibatalkan. Tidak ada API Key yang disimpan.")
        return
    if stripped.startswith("/"):
        await message.answer("Kirim API Key sebagai teks saja atau ketik /cancel untuk membatalkan.")
        return

    # Delete the source message as early as possible. Do not log or echo the secret.
    try:
        await message.delete()
    except Exception:
        # Deletion is best-effort; keep the key out of all bot logs and replies regardless.
        pass
    await state.clear()

    api_key = stripped
    if api_key.lower().startswith("bearer "):
        api_key = api_key[7:].strip()
    if not api_key or len(api_key) > 512 or re.search(r"\s", api_key):
        await message.answer(
            "Format API Key tidak valid. Pesan sumber sudah diminta untuk dihapus. "
            "Ketik /connect untuk mencoba lagi; jangan kirim key ke grup."
        )
        return

    settings = get_settings()
    try:
        client = AugestelClient.from_settings(api_key=SecretStr(api_key))
        # The official, read-only endpoint validates the key without changing account data.
        await client.list_numbers(page=1, per_page=1)
    except AugestelIntegrationDisabled:
        await message.answer(
            "Integrasi Augestel sedang dinonaktifkan atau key tidak tersedia. "
            "Pengelola bot perlu memeriksa konfigurasi."
        )
        return
    except AugestelIntegrationError as exc:
        logger.info("Augestel API key validation failed with a sanitized integration error.")
        if "rejected the API key" in str(exc):
            await message.answer(
                "Augestel menolak API Key (HTTP 401). Tidak ada key yang disimpan. "
                "Periksa key di dashboard dan coba /connect lagi."
            )
        else:
            await message.answer(
                "API Key belum berhasil divalidasi melalui endpoint My Numbers. "
                "Tidak ada key yang disimpan. Coba lagi nanti atau periksa status API Augestel."
            )
        return

    try:
        encrypted_key = encrypt_api_key(api_key)
        await save_api_key_for_user(message.from_user.id, encrypted_key)
    except SecretStorageError:
        await message.answer(
            "Key berhasil divalidasi, tetapi penyimpanan terenkripsi gagal. "
            "Key tidak disimpan. Hubungi pengelola bot untuk memeriksa konfigurasi enkripsi."
        )
        return
    except Exception:
        logger.exception("Could not persist a validated Augestel API key")
        await message.answer(
            "Key berhasil divalidasi, tetapi database gagal menyimpannya. "
            "Key tidak dapat dipastikan tersimpan; jalankan /connect lagi setelah database diperbaiki."
        )
        return
    finally:
        api_key = ""

    try:
        await record_operation(
            message.from_user.id,
            "connect_account",
            "connected",
            result_summary="Augestel API key validated and stored encrypted; key value omitted.",
        )
    except Exception:
        logger.exception("Could not record successful API-key connection event")

    await message.answer(
        "<b>✅ Akun Augestel terhubung</b>\n\n"
        "API Key berhasil divalidasi dan disimpan secara terenkripsi. Bot tidak menyimpan "
        "key dalam riwayat aktivitas dan tidak akan menampilkannya kembali.\n\n"
        "<b>Jangan membagikan API Key.</b> Jika key terekspos, lakukan regenerate di dashboard "
        "Augestel lalu hubungkan ulang dengan <code>/connect</code>.\n\n"
        "Kamu bisa mulai dengan <code>/numbers</code>."
    )


@router.message(Command("account"))
async def account_command(message: Message) -> None:
    await _show_account_status(message)


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
    key_status = "Tersimpan terenkripsi" if status.has_api_key else "Belum terhubung"
    await message.answer(
        "<b>My Account</b>\n"
        f"Provider: <code>{escape(status.provider)}</code>\n"
        f"Status: <code>{_status_label(status.connection_status)}</code>\n"
        f"API Key: <code>{key_status}</code>\n"
        f"Validasi terakhir: <code>{validated}</code>"
    )


@router.message(Command("disconnect"))
async def disconnect_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _disconnect_account(message)


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
                result_summary="Connection state and encrypted API key cleared for this Telegram user.",
            )
        except Exception:
            logger.exception("Could not record account disconnect event")
        await message.answer(
            "Koneksi Augestel diputus. API Key terenkripsi sudah dihapus dari database bot. "
            "Untuk menghubungkan lagi, gunakan /connect."
        )
    else:
        await message.answer("Belum ada koneksi Augestel yang perlu diputuskan.")


@router.callback_query(lambda query: query.data == "menu:account")
async def account_menu(query: CallbackQuery) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        await _show_account_status_for_user(query.message, query.from_user.id)


async def _show_account_status_for_user(message: Message, telegram_id: int) -> None:
    try:
        status = await get_account_status(telegram_id)
    except Exception:
        logger.exception("Could not load account status from menu")
        await message.answer("Gagal membaca status akun. Periksa koneksi database.")
        return
    validated = (
        status.last_validated_at.strftime("%Y-%m-%d %H:%M UTC")
        if status.last_validated_at
        else "Belum pernah"
    )
    key_status = "Tersimpan terenkripsi" if status.has_api_key else "Belum terhubung"
    await message.answer(
        "<b>My Account</b>\n"
        f"Provider: <code>{escape(status.provider)}</code>\n"
        f"Status: <code>{_status_label(status.connection_status)}</code>\n"
        f"API Key: <code>{key_status}</code>\n"
        f"Validasi terakhir: <code>{validated}</code>"
    )


@router.callback_query(lambda query: query.data == "menu:disconnect")
async def disconnect_menu(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.clear()
    if isinstance(query.message, Message):
        # For callback queries, use the user's ID instead of the bot's message sender.
        user = query.from_user
        try:
            disconnected = await disconnect_account(user.id)
        except Exception:
            logger.exception("Could not disconnect account from menu")
            await query.message.answer("Gagal memutuskan koneksi. Periksa koneksi database.")
            return
        if disconnected:
            try:
                await record_operation(
                    user.id,
                    "disconnect_account",
                    "disconnected",
                    result_summary="Connection state and encrypted API key cleared for this Telegram user.",
                )
            except Exception:
                logger.exception("Could not record account disconnect event")
            await query.message.answer(
                "Koneksi Augestel diputus dan API Key terenkripsi dihapus. Gunakan /connect untuk menghubungkan ulang."
            )
        else:
            await query.message.answer("Belum ada koneksi Augestel yang perlu diputuskan.")
