import logging
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import confirm_return_all, numbers_pagination
from app.integrations.augestel import (
    AugestelClient,
    AugestelIntegrationDisabled,
    AugestelIntegrationError,
)
from app.services.add_number_draft import AddNumberDraftError, parse_add_number_draft
from app.services.accounts import load_api_key_for_user
from app.services.operation_history import list_operations, record_operation
from app.services.secret_store import SecretStorageError

router = Router()
logger = logging.getLogger(__name__)


class AugestelAccountNotConnected(RuntimeError):
    pass


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
        "Integrasi Augestel masih dalam mode aman karena endpoint/fitur ini belum diverifikasi. "
        "Tidak ada request ke Augestel yang dikirim."
    )


def _format_number_page(payload: dict) -> tuple[str, object | None]:
    records = payload["data"]
    pagination = payload["pagination"]
    page = pagination["current_page"]
    last_page = pagination["last_page"]
    per_page = pagination["per_page"]
    total = pagination["total"]

    lines = [
        "<b>📱 My Numbers</b>",
        f"Total nomor: <b>{total}</b>",
        f"Halaman <b>{page}</b> dari <b>{max(1, last_page)}</b> · {per_page} per halaman",
        "",
    ]
    if not records:
        lines.append("Tidak ada nomor pada halaman ini.")
    else:
        for index, record in enumerate(records, start=1):
            number = escape(record["number"])
            range_name = escape(record["range_name"])
            rate_value = record.get("a2p_rate")
            if isinstance(rate_value, (int, float)) and not isinstance(rate_value, bool):
                rate = f"{rate_value:.4f}"
            else:
                rate = "—"
            limit_value = record.get("portal_limit_a2p")
            limit = str(limit_value) if isinstance(limit_value, int) and not isinstance(limit_value, bool) else "—"
            last_message = record.get("last_message_at")
            if not isinstance(last_message, str) or not last_message:
                last_message = "Belum ada data"
            else:
                last_message = escape(last_message)
            lines.extend(
                [
                    f"<b>{index}. {number}</b> · {range_name}",
                    f"Tarif A2P: <code>{rate}</code> · Portal limit: <code>{limit}</code>",
                    f"Pesan terakhir: <code>{last_message}</code>",
                    "",
                ]
            )
    return "\n".join(lines).strip(), numbers_pagination(page, last_page)


async def _load_number_page(page: int) -> tuple[str, object | None]:
    client = AugestelClient.from_settings()
    payload = await client.list_numbers(page=page, per_page=20)
    return _format_number_page(payload)


async def _show_numbers(message: Message, page: int = 1) -> None:
    if page < 1:
        await message.answer("Nomor halaman harus minimal 1.")
        return
    try:
        text, keyboard = await _load_number_page(page)
    except AugestelIntegrationDisabled:
        await message.answer(
            "<b>My Numbers belum terhubung.</b>\n"
            "Isi <code>AUGESTEL_API_KEY</code> pada file <code>.env</code>, pastikan Base URL "
            "API benar, lalu aktifkan integrasi setelah konfigurasi siap. "
            "Jangan kirim API key melalui Telegram."
        )
        return
    except AugestelIntegrationError as exc:
        logger.warning("Augestel My Numbers request failed: %s", str(exc))
        await message.answer(f"Gagal mengambil daftar nomor: {escape(str(exc))}")
        return
    except Exception:
        logger.exception("Unexpected error loading Augestel My Numbers")
        await message.answer("Terjadi kesalahan saat mengambil daftar nomor. Coba lagi nanti.")
        return

    if requester_id is not None:
        await _audit(
            requester_id,
            "list_numbers",
            "success",
            f"Fetched My Numbers page {page}; number details are not stored in operation history.",
        )
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("numbers"))
async def numbers_command(message: Message) -> None:
    text = message.text or ""
    parts = text.split()
    page = 1
    if len(parts) > 2:
        await message.answer("Format: <code>/numbers</code> atau <code>/numbers 2</code>")
        return
    if len(parts) == 2:
        try:
            page = int(parts[1])
        except ValueError:
            await message.answer("Nomor halaman harus berupa bilangan bulat. Contoh: <code>/numbers 2</code>")
            return
    await _show_numbers(message, page)


@router.callback_query(lambda query: query.data == "menu:numbers")
async def numbers_menu(query: CallbackQuery) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        await _show_numbers(query.message, 1, telegram_id=query.from_user.id)


@router.callback_query(lambda query: bool(query.data and query.data.startswith("numbers:page:")))
async def numbers_page_callback(query: CallbackQuery) -> None:
    data = query.data or ""
    try:
        page = int(data.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await query.answer("Halaman tidak valid.", show_alert=True)
        return
    if page < 1:
        await query.answer("Halaman tidak valid.", show_alert=True)
        return
    await query.answer()
    if not isinstance(query.message, Message):
        return
    try:
        text, keyboard = await _load_number_page(query.from_user.id, page)
    except AugestelAccountNotConnected:
        await query.message.answer(
            "My Numbers belum terhubung. Gunakan /connect di chat pribadi untuk menyambungkan API Key."
        )
        return
    except SecretStorageError:
        logger.warning("Could not decrypt API key for Telegram user %s", query.from_user.id)
        await query.message.answer(
            "Key tersimpan tidak dapat dibuka. Periksa konfigurasi enkripsi, lalu hubungkan ulang dengan /connect."
        )
        return
    except AugestelIntegrationDisabled:
        await query.message.answer(
            "Integrasi Augestel sedang dinonaktifkan oleh pengelola bot."
        )
        return
    except AugestelIntegrationError as exc:
        logger.warning("Augestel My Numbers pagination failed: %s", str(exc))
        await query.message.answer(f"Gagal membuka halaman: {escape(str(exc))}")
        return
    except Exception:
        logger.exception("Unexpected error loading Augestel My Numbers page")
        await query.message.answer("Terjadi kesalahan saat mengambil halaman nomor.")
        return

    if query.from_user is not None:
        await _audit(
            query.from_user.id,
            "list_numbers",
            "success",
            f"Fetched My Numbers page {page}; number details are not stored in operation history.",
        )
    await query.message.edit_text(text, reply_markup=keyboard)


@router.message(Command("addnumber"))
async def add_number_command(message: Message) -> None:
    text = message.text or ""
    _, _, arguments = text.partition(" ")
    if not arguments.strip():
        await message.answer(
            "<b>Draft Add Number</b>\n\n"
            "Format: <code>/addnumber &lt;termination_id&gt; "
            "&lt;termination_term_id&gt; &lt;count&gt; &lt;sort_type&gt;</code>\n"
            "Contoh format: <code>/addnumber term_123 term_456 5 asc</code>\n\n"
            "Ini hanya memvalidasi draft lokal. Nilai ID harus diperoleh dari akun Anda. "
            "Token CSRF/session tidak boleh dimasukkan. Draft yang valid tetap tidak dikirim "
            "ke Augestel karena autentikasi integrasi belum tersedia."
        )
        return

    try:
        draft = parse_add_number_draft(arguments)
    except AddNumberDraftError as exc:
        await message.answer(f"Parameter tidak valid: {escape(str(exc))}")
        return

    if message.from_user is not None:
        await _audit(
            message.from_user.id,
            "add_number",
            "draft_prepared_not_sent",
            "Local draft validated; no request sent because Augestel authentication is not enabled.",
        )
    await message.answer(
        "<b>Draft Add Number tervalidasi</b>\n"
        f"Termination ID: <code>{escape(draft.termination_id)}</code>\n"
        f"Billing term ID: <code>{escape(draft.termination_term_id)}</code>\n"
        f"Jumlah: <code>{draft.count}</code>\n"
        f"Sort type: <code>{escape(draft.sort_type)}</code>\n\n"
        "<b>Belum dieksekusi.</b> Tidak ada request dikirim ke Augestel. "
        "Autentikasi yang disetujui dan kontrak request masih perlu dikonfirmasi."
    )


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
