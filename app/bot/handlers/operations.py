import logging
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import confirm_return_all
from app.services.operation_history import list_operations, record_operation

router = Router()
logger = logging.getLogger(__name__)


async def _audit(telegram_id: int, operation: str, status: str, summary: str) -> None:
    try:
        await record_operation(
            telegram_id,
            operation,
            status,
            result_summary=summary,
        )
    except Exception:
        # Audit failures are logged but must never expose credentials or stop a safe refusal.
        logger.exception("Could not record operation event: %s (%s)", operation, status)


async def _not_enabled(message: Message, feature: str, operation: str | None = None) -> None:
    if message.from_user is not None and operation:
        await _audit(
            message.from_user.id,
            operation,
            "blocked_integration_disabled",
            "No request was sent; Augestel integration is disabled.",
        )
    await message.answer(
        f"<b>{escape(feature)}</b> belum dieksekusi.\n"
        "Integrasi Augestel masih dalam mode aman karena metode autentikasi dan izin "
        "endpoint perlu divalidasi terlebih dahulu. Tidak ada request ke Augestel yang dikirim."
    )


@router.message(Command("addnumber"))
async def add_number_command(message: Message) -> None:
    await _not_enabled(message, "Add Number", "add_number")


@router.message(Command("download"))
async def download_command(message: Message) -> None:
    await _not_enabled(message, "Download Numbers", "download_numbers")


@router.message(Command("returnall"))
async def return_all_command(message: Message) -> None:
    if message.from_user is not None:
        await _audit(
            message.from_user.id,
            "return_all",
            "confirmation_requested",
            "Confirmation requested; no request has been sent.",
        )
    await message.answer(
        "<b>⚠️ Return All</b>\n\n"
        "Tindakan ini dapat mengembalikan seluruh nomor pada akun Augestel yang terhubung.\n"
        "Saat ini integrasi belum diaktifkan, jadi tombol konfirmasi tidak akan mengirim request.",
        reply_markup=confirm_return_all(),
    )


@router.message(Command("history"))
async def history_command(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Identitas Telegram tidak tersedia.")
        return
    try:
        records = await list_operations(message.from_user.id, limit=10)
    except Exception:
        logger.exception("Could not retrieve operation history")
        await message.answer("Gagal membaca riwayat. Periksa koneksi database.")
        return
    if not records:
        await message.answer("Belum ada riwayat operasi yang tercatat.")
        return
    lines = ["<b>Operation History — 10 terbaru</b>"]
    for item in records:
        created = item.created_at.strftime("%Y-%m-%d %H:%M UTC")
        summary = escape(item.result_summary or "")
        error = f" · <code>{escape(item.error_code)}</code>" if item.error_code else ""
        lines.append(
            f"\n<b>{escape(item.operation_type)}</b> — <code>{escape(item.status)}</code>"
            f"\n<code>{created}</code>{error}"
            + (f"\n{summary}" if summary else "")
        )
    await message.answer("\n".join(lines))


@router.message(Command("cancel"))
async def cancel_command(message: Message) -> None:
    await message.answer("Tidak ada operasi aktif yang dieksekusi.")


@router.callback_query(lambda query: query.data == "menu:add")
async def add_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        if query.from_user:
            await _audit(
                query.from_user.id, "add_number", "blocked_integration_disabled",
                "No request was sent; Augestel integration is disabled."
            )
        await _not_enabled(query.message, "Add Number")


@router.callback_query(lambda query: query.data == "menu:download")
async def download_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        if query.from_user:
            await _audit(
                query.from_user.id, "download_numbers", "blocked_integration_disabled",
                "No request was sent; Augestel integration is disabled."
            )
        await _not_enabled(query.message, "Download Numbers")


@router.callback_query(lambda query: query.data == "menu:return_all")
async def return_all_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        if query.from_user:
            await _audit(
                query.from_user.id,
                "return_all",
                "confirmation_requested",
                "Confirmation requested; no request has been sent.",
            )
        await query.message.answer(
            "<b>⚠️ Return All</b>\n\n"
            "Tindakan ini dapat mengembalikan seluruh nomor. Integrasi masih dinonaktifkan; "
            "konfirmasi tidak akan menjalankan request.",
            reply_markup=confirm_return_all(),
        )


@router.callback_query(lambda query: query.data == "return_all:confirm")
async def confirm_return_all_callback(query: CallbackQuery) -> None:
    await query.answer("Integrasi belum diaktifkan.", show_alert=True)
    if query.from_user:
        await _audit(
            query.from_user.id,
            "return_all",
            "blocked_integration_disabled",
            "User confirmed, but no request was sent because integration is disabled.",
        )
    if query.message:
        await query.message.answer(
            "Operasi tidak dijalankan. Integrasi Augestel masih dinonaktifkan."
        )


@router.callback_query(lambda query: query.data == "return_all:cancel")
async def cancel_return_all_callback(query: CallbackQuery) -> None:
    await query.answer("Dibatalkan.")
    if query.from_user:
        await _audit(
            query.from_user.id,
            "return_all",
            "cancelled",
            "User cancelled before execution; no request was sent.",
        )
    if query.message:
        await query.message.answer("Return All dibatalkan. Tidak ada request yang dikirim.")


@router.callback_query(lambda query: query.data == "menu:history")
async def history_menu(query: CallbackQuery) -> None:
    await query.answer()
    if query.message and query.from_user is not None:
        try:
            records = await list_operations(query.from_user.id, limit=10)
        except Exception:
            logger.exception("Could not retrieve operation history from menu")
            await query.message.answer("Gagal membaca riwayat. Periksa koneksi database.")
            return
        if not records:
            await query.message.answer("Belum ada riwayat operasi yang tercatat.")
            return
        lines = ["<b>Operation History — 10 terbaru</b>"]
        for item in records:
            created = item.created_at.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(
                f"\n<b>{escape(item.operation_type)}</b> — <code>{escape(item.status)}</code>"
                f"\n<code>{created}</code>"
                + (f"\n{escape(item.result_summary)}" if item.result_summary else "")
            )
        await query.message.answer("\n".join(lines))
