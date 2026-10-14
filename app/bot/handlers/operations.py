import logging
from html import escape

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import confirm_add_number, confirm_return_all, numbers_pagination
from app.integrations.augestel import (
    AugestelClient,
    AugestelIntegrationDisabled,
    AugestelIntegrationError,
    AugestelOperationOutcomeUnknown,
)
from app.services.accounts import load_api_key_for_user
from app.services.add_number_draft import AddNumberDraftError, parse_add_number_draft
from app.services.operation_history import list_operations, record_operation
from app.services.secret_store import SecretStorageError

router = Router()
logger = logging.getLogger(__name__)


class AugestelAccountNotConnected(RuntimeError):
    """The Telegram user has not securely connected their own Augestel API key."""


class AddNumberFlow(StatesGroup):
    waiting_confirmation = State()


class ReturnAllFlow(StatesGroup):
    waiting_confirmation = State()


async def _connected_client(telegram_id: int) -> AugestelClient:
    api_key = await load_api_key_for_user(telegram_id)
    if api_key is None:
        raise AugestelAccountNotConnected
    return AugestelClient.from_settings(api_key=api_key)


async def _audit(telegram_id: int, operation: str, status: str, summary: str) -> None:
    try:
        await record_operation(
            telegram_id,
            operation,
            status,
            result_summary=summary,
        )
    except Exception:
        # Never place credentials or full API responses in activity history.
        logger.exception("Could not record operation event: %s (%s)", operation, status)


async def _not_enabled(message: Message, feature: str, operation: str | None = None) -> None:
    if message.from_user is not None and operation:
        await _audit(
            message.from_user.id,
            operation,
            "blocked_integration_disabled",
            "No request was sent; this operation is not enabled.",
        )
    await message.answer(
        f"<b>{escape(feature)}</b> belum dieksekusi.\n"
        "Endpoint API untuk fitur ini belum diverifikasi. Tidak ada request yang dikirim."
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
            limit = (
                str(limit_value)
                if isinstance(limit_value, int) and not isinstance(limit_value, bool)
                else "—"
            )
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


async def _load_number_page(telegram_id: int, page: int) -> tuple[str, object | None]:
    api_key = await load_api_key_for_user(telegram_id)
    if api_key is None:
        raise AugestelAccountNotConnected
    client = AugestelClient.from_settings(api_key=api_key)
    payload = await client.list_numbers(page=page, per_page=20)
    return _format_number_page(payload)


async def _show_numbers(
    message: Message,
    page: int = 1,
    *,
    telegram_id: int | None = None,
) -> None:
    if message.chat.type != ChatType.PRIVATE:
        await message.answer("Demi keamanan, gunakan My Numbers di chat pribadi bot.")
        return
    if page < 1:
        await message.answer("Nomor halaman harus minimal 1.")
        return

    requester_id = telegram_id or (message.from_user.id if message.from_user else None)
    if requester_id is None:
        await message.answer("Identitas Telegram tidak tersedia.")
        return

    try:
        text, keyboard = await _load_number_page(requester_id, page)
    except AugestelAccountNotConnected:
        await message.answer(
            "<b>My Numbers belum terhubung.</b>\n"
            "Ketik <code>/connect</code> di chat pribadi lalu kirim API Key. "
            "Jangan bagikan API Key ke orang lain atau grup."
        )
        return
    except SecretStorageError:
        logger.warning("Could not decrypt API key for Telegram user %s", requester_id)
        await message.answer(
            "Key tersimpan tidak dapat dibuka. Pengelola perlu memeriksa konfigurasi enkripsi; "
            "setelah itu hubungkan ulang dengan /connect."
        )
        return
    except AugestelIntegrationDisabled:
        await message.answer("Integrasi Augestel sedang dinonaktifkan oleh pengelola bot.")
        return
    except AugestelIntegrationError as exc:
        logger.warning("Augestel My Numbers request failed: %s", str(exc))
        await message.answer(f"Gagal mengambil daftar nomor: {escape(str(exc))}")
        return
    except Exception:
        logger.exception("Unexpected error loading Augestel My Numbers")
        await message.answer("Terjadi kesalahan saat mengambil daftar nomor. Coba lagi nanti.")
        return

    await _audit(
        requester_id,
        "list_numbers",
        "success",
        f"Fetched My Numbers page {page}; number details and API key are not stored in history.",
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
    # Do not reveal account numbers into group chats.
    if query.message.chat.type != ChatType.PRIVATE:
        await query.message.answer("Demi keamanan, gunakan My Numbers di chat pribadi bot.")
        return
    try:
        text, keyboard = await _load_number_page(query.from_user.id, page)
    except AugestelAccountNotConnected:
        await query.message.answer("My Numbers belum terhubung. Gunakan /connect di chat pribadi.")
        return
    except SecretStorageError:
        logger.warning("Could not decrypt API key for Telegram user %s", query.from_user.id)
        await query.message.answer("Key tersimpan tidak dapat dibuka. Periksa konfigurasi enkripsi.")
        return
    except AugestelIntegrationDisabled:
        await query.message.answer("Integrasi Augestel sedang dinonaktifkan oleh pengelola bot.")
        return
    except AugestelIntegrationError as exc:
        logger.warning("Augestel My Numbers pagination failed: %s", str(exc))
        await query.message.answer(f"Gagal membuka halaman: {escape(str(exc))}")
        return
    except Exception:
        logger.exception("Unexpected error loading Augestel My Numbers page")
        await query.message.answer("Terjadi kesalahan saat mengambil halaman nomor.")
        return

    await _audit(
        query.from_user.id,
        "list_numbers",
        "success",
        f"Fetched My Numbers page {page}; number details and API key are not stored in history.",
    )
    await query.message.edit_text(text, reply_markup=keyboard)


@router.message(Command("terminations"))
async def terminations_command(message: Message) -> None:
    if message.chat.type != ChatType.PRIVATE:
        await message.answer("Demi keamanan, daftar termination hanya tersedia di chat pribadi bot.")
        return
    if message.from_user is None:
        await message.answer("Identitas Telegram tidak tersedia.")
        return
    try:
        client = await _connected_client(message.from_user.id)
        payload = await client.list_terminations()
    except AugestelAccountNotConnected:
        await message.answer("Hubungkan akun terlebih dahulu dengan <code>/connect</code> di chat pribadi.")
        return
    except SecretStorageError:
        await message.answer("API Key tersimpan tidak bisa dibuka. Hubungi pengelola bot.")
        return
    except AugestelIntegrationDisabled as exc:
        await message.answer(escape(str(exc)))
        return
    except AugestelIntegrationError as exc:
        logger.warning("Augestel termination metadata request failed: %s", str(exc))
        await message.answer(
            "Tidak dapat membaca daftar termination dari rute website. "
            f"{escape(str(exc))}"
        )
        return
    except Exception as exc:
        logger.error(
            "Unexpected termination metadata error for Telegram user %s (%s)",
            message.from_user.id,
            type(exc).__name__,
        )
        await message.answer("Terjadi kesalahan saat membaca daftar termination.")
        return

    items = payload.get("terminations", [])
    if not items:
        await message.answer("Augestel tidak mengembalikan pilihan termination untuk akun ini.")
        return

    lines = [
        "<b>Daftar termination Augestel</b>",
        "Gunakan ID di bawah untuk perintah <code>/addnumber</code>.",
        "Nilai <code>sort_type</code> harus persis sesuai metadata.",
        "",
    ]
    truncated = False
    for item in items:
        ident = escape(str(item.get("id", "")))
        name = escape(str(item.get("name", "Unknown")))
        available = item.get("available_count")
        max_per_request = item.get("max_per_request")
        sort_type = escape(str(item.get("number_sort_type") or "—"))
        lines.append(
            f"<b>{name}</b> · ID <code>{ident}</code>\n"
            f"Operator: {escape(str(item.get('operator') or '—'))} · "
            f"Country: {escape(str(item.get('country_code') or '—'))}\n"
            f"Tersedia: <code>{available if isinstance(available, int) else '—'}</code> · "
            f"Batas/request: <code>{max_per_request if isinstance(max_per_request, int) else '—'}</code>\n"
            f"sort_type: <code>{sort_type}</code>"
        )
        for term in item.get("terms", [])[:10]:
            term_id = escape(str(term.get("id", "")))
            term_name = escape(str(term.get("term") or "—"))
            rate = term.get("a2p_rate")
            if isinstance(rate, (int, float)) and not isinstance(rate, bool):
                rate_text = f"{rate:.4f}"
            else:
                rate_text = "—"
            default_label = " (default)" if term.get("is_default") else ""
            lines.append(
                f"  • Term ID <code>{term_id}</code> · {term_name} · "
                f"A2P <code>{rate_text}</code>{default_label}"
            )
        lines.append("")
        if len("\n".join(lines)) > 3400:
            truncated = True
            lines = lines[:-1]
            break

    if truncated:
        lines.append("Daftar dipotong agar muat di Telegram. Pilih ID yang sudah tampil.")
    lines.extend(
        [
            "",
            "Format:",
            "<code>/addnumber &lt;termination_id&gt; &lt;termination_term_id&gt; &lt;count&gt; &lt;sort_type&gt;</code>",
            "Contoh format: <code>/addnumber 12345 123456 5 random</code> (nilai contoh saja).",
        ]
    )
    await message.answer("\n".join(lines))


@router.message(Command("addnumber"))
async def add_number_command(message: Message, state: FSMContext) -> None:
    if message.chat.type != ChatType.PRIVATE:
        await message.answer("Demi keamanan, Add Number hanya tersedia di chat pribadi bot.")
        return
    await state.clear()

    raw = message.text or ""
    _, _, arguments = raw.partition(" ")
    if not arguments.strip():
        await message.answer(
            "<b>➕ Add Number</b>\n\n"
            "Format: <code>/addnumber &lt;termination_id&gt; "
            "&lt;termination_term_id&gt; &lt;count&gt; &lt;sort_type&gt;</code>\n"
            "Contoh format: <code>/addnumber 12345 123456 5 random</code>\n\n"
            "ID harus berasal dari informasi akun/terminasi Augestel kamu. Nilai contoh di atas "
            "hanya ilustrasi. Setelah validasi, bot akan menampilkan ringkasan dan meminta konfirmasi. "
            "Endpoint website yang teramati belum menjadi API publik terdokumentasi, sehingga eksekusi "
            "tetap membutuhkan <code>AUGESTEL_CUSTOM_WRITE_ENABLED=true</code> di konfigurasi operator."
        )
        return

    if message.from_user is None:
        await message.answer("Identitas Telegram tidak tersedia.")
        return

    try:
        await _connected_client(message.from_user.id)
    except AugestelAccountNotConnected:
        await message.answer("Hubungkan akun terlebih dahulu dengan <code>/connect</code> di chat pribadi.")
        return
    except SecretStorageError:
        await message.answer("API Key tersimpan tidak bisa dibuka. Hubungi pengelola bot.")
        return

    try:
        draft = parse_add_number_draft(arguments)
    except AddNumberDraftError as exc:
        await message.answer(f"Parameter tidak valid: {escape(str(exc))}")
        return

    await state.set_state(AddNumberFlow.waiting_confirmation)
    await state.set_data(
        {
            "termination_id": draft.termination_id,
            "termination_term_id": draft.termination_term_id,
            "count": draft.count,
            "sort_type": draft.sort_type,
        }
    )
    await _audit(
        message.from_user.id,
        "add_number",
        "confirmation_requested",
        "Validated Add Number draft; no request has been sent.",
        )
    await message.answer(
        "<b>Konfirmasi Add Number</b>\n\n"
        f"Termination ID: <code>{escape(draft.termination_id)}</code>\n"
        f"Term ID: <code>{escape(draft.termination_term_id)}</code>\n"
        f"Jumlah: <b>{draft.count}</b>\n"
        f"Sort type: <code>{escape(draft.sort_type)}</code>\n\n"
        "Pastikan data benar sebelum melanjutkan. Jika rute website membutuhkan CSRF/browser session, "
        "bot akan berhenti tanpa melewati perlindungan tersebut.",
        reply_markup=confirm_add_number(),
    )


@router.callback_query(lambda query: query.data == "add_number:cancel")
async def cancel_add_number_callback(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await query.answer("Add Number dibatalkan.")
    if isinstance(query.message, Message):
        if query.from_user:
            await _audit(
                query.from_user.id,
                "add_number",
                "cancelled",
                "User cancelled before any write request was sent.",
            )
        await query.message.answer("Add Number dibatalkan. Tidak ada request yang dikirim.")


@router.callback_query(lambda query: query.data == "add_number:confirm")
async def confirm_add_number_callback(query: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(query.message, Message) or query.message.chat.type != ChatType.PRIVATE:
        await query.answer("Konfirmasi hanya tersedia di chat pribadi.", show_alert=True)
        await state.clear()
        return
    data = await state.get_data()
    required = ("termination_id", "termination_term_id", "count", "sort_type")
    if await state.get_state() != AddNumberFlow.waiting_confirmation.state or not all(
        key in data for key in required
    ):
        await query.answer("Draft tidak tersedia atau sudah kedaluwarsa. Mulai lagi dengan /addnumber.", show_alert=True)
        await state.clear()
        return

    # Clear confirmation state before I/O so a double-click cannot repeat this POST.
    await state.clear()
    await query.answer("Memproses Add Number…")
    user = query.from_user
    try:
        client = await _connected_client(user.id)
        payload = {
            "termination_id": data["termination_id"],
            "termination_term_id": data["termination_term_id"],
            "count": data["count"],
            "sort_type": data["sort_type"],
        }
        result = await client.add_numbers(payload)
    except AugestelAccountNotConnected:
        await query.message.answer("Akun belum terhubung. Gunakan /connect lalu ulangi Add Number.")
        return
    except SecretStorageError:
        await query.message.answer("API Key tersimpan tidak bisa dibuka. Hubungi pengelola bot.")
        return
    except AugestelIntegrationDisabled as exc:
        await _audit(user.id, "add_number", "blocked_write_disabled", "No request was sent.")
        await query.message.answer(escape(str(exc)))
        return
    except AugestelOperationOutcomeUnknown:
        await _audit(
            user.id,
            "add_number",
            "outcome_unknown",
            "Write request outcome was uncertain; do not retry until My Numbers is checked.",
            )
        await query.message.answer(
            "⚠️ Hasil Add Number belum bisa dipastikan. Jangan tekan ulang dulu. "
            "Periksa <code>/numbers</code> dan portal Augestel untuk memastikan apakah nomor sudah ditambahkan."
        )
        return
    except AugestelIntegrationError as exc:
        await _audit(
            user.id,
            "add_number",
            "failed",
            "Augestel did not provide a confirmed success response; no automatic retry was made.",
        )
        await query.message.answer(f"Add Number gagal: {escape(str(exc))}")
        return
    except Exception as exc:
        logger.error("Unexpected Add Number error for Telegram user %s (%s)", user.id, type(exc).__name__)
        await _audit(user.id, "add_number", "outcome_unknown", "Unexpected write error; check account before retry.")
        await query.message.answer(
            "Respons Add Number tidak dapat dipastikan. Periksa <code>/numbers</code> sebelum mencoba lagi."
        )
        return

    await _audit(
        user.id,
        "add_number",
        "success",
        f"Augestel returned success for requested count {data['count']}; verify assigned numbers with /numbers.",
        )
    await query.message.answer(
        f"✅ Augestel mengembalikan status sukses untuk permintaan {data['count']} nomor. "
        "Gunakan <code>/numbers</code> untuk memverifikasi hasil sebenarnya."
    )


@router.message(Command("download"))
async def download_command(message: Message) -> None:
    await _not_enabled(message, "Download Numbers", "download_numbers")


async def _show_return_all_preview(
    message: Message,
    state: FSMContext,
    *,
    telegram_id: int | None = None,
) -> None:
    if message.chat.type != ChatType.PRIVATE:
        await message.answer("Demi keamanan, Return All hanya tersedia di chat pribadi bot.")
        return
    await state.clear()
    user_id = telegram_id or (message.from_user.id if message.from_user else None)
    if user_id is None:
        await message.answer("Identitas Telegram tidak tersedia.")
        return
    try:
        client = await _connected_client(user_id)
        numbers = await client.list_numbers(page=1, per_page=1)
    except AugestelAccountNotConnected:
        await message.answer("Hubungkan akun terlebih dahulu dengan <code>/connect</code> di chat pribadi.")
        return
    except SecretStorageError:
        await message.answer("API Key tersimpan tidak bisa dibuka. Hubungi pengelola bot.")
        return
    except AugestelIntegrationDisabled:
        await message.answer("Integrasi Augestel sedang dinonaktifkan oleh pengelola bot.")
        return
    except AugestelIntegrationError as exc:
        await message.answer(f"Tidak dapat memeriksa jumlah nomor saat ini: {escape(str(exc))}")
        return
    except Exception as exc:
        logger.error("Could not preview Return All for Telegram user %s (%s)", user_id, type(exc).__name__)
        await message.answer("Gagal memeriksa jumlah nomor. Tidak ada perubahan yang dilakukan.")
        return

    total = numbers["pagination"]["total"]
    if total == 0:
        await state.clear()
        await message.answer("Akun ini saat ini memiliki 0 nomor. Return All tidak diperlukan.")
        return

    await state.set_state(ReturnAllFlow.waiting_confirmation)
    await state.set_data({"expected_total": total})
    await _audit(
        user_id,
        "return_all",
        "confirmation_requested",
        f"Preview showed {total} assigned numbers; no request has been sent.",
    )
    await message.answer(
        "<b>⚠️ Konfirmasi Return All</b>\n\n"
        f"API saat ini melaporkan <b>{total}</b> nomor pada akun yang terhubung.\n"
        "Jika diteruskan, tindakan ini akan mencoba mengembalikan semua nomor pada akun tersebut. "
        "Tindakan tidak dapat dibatalkan melalui bot.\n\n"
        "Rute Return All berasal dari pengamatan alur website, bukan dokumentasi API publik. "
        "Jika server memerlukan sesi browser/CSRF, bot tidak akan melewatinya. Jika hasil request tidak pasti, "
        "bot tidak akan mengulang otomatis.",
        reply_markup=confirm_return_all(),
    )


@router.message(Command("returnall"))
async def return_all_command(message: Message, state: FSMContext) -> None:
    await _show_return_all_preview(message, state)


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
    if isinstance(query.message, Message):
        if query.message.chat.type != ChatType.PRIVATE:
            await query.message.answer("Demi keamanan, Add Number hanya tersedia di chat pribadi bot.")
            return
        await query.message.answer(
            "<b>➕ Add Number</b>\n\n"
            "Kirim perintah dengan format:\n"
            "<code>/addnumber &lt;termination_id&gt; &lt;termination_term_id&gt; &lt;count&gt; &lt;sort_type&gt;</code>\n"
            "Contoh format: <code>/addnumber 12345 123456 5 random</code>\n\n"
            "termination_id dan termination_term_id harus berupa ID numerik dari akun Augestel; sort_type harus cocok dengan number_sort_type pada metadata termination. Bot akan meminta konfirmasi sebelum mengirim request."
        )


@router.callback_query(lambda query: query.data == "menu:download")
async def download_menu(query: CallbackQuery) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        await _audit(
            query.from_user.id,
            "download_numbers",
            "blocked_integration_disabled",
            "No request was sent; documented export endpoint is not available.",
        )
        await _not_enabled(query.message, "Download Numbers")


@router.callback_query(lambda query: query.data == "menu:return_all")
async def return_all_menu(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        await _show_return_all_preview(query.message, state, telegram_id=query.from_user.id)


@router.callback_query(lambda query: query.data == "return_all:confirm")
async def confirm_return_all_callback(query: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(query.message, Message) or query.message.chat.type != ChatType.PRIVATE:
        await query.answer("Konfirmasi hanya tersedia di chat pribadi.", show_alert=True)
        await state.clear()
        return
    data = await state.get_data()
    if (
        await state.get_state() != ReturnAllFlow.waiting_confirmation.state
        or not isinstance(data.get("expected_total"), int)
    ):
        await query.answer("Konfirmasi tidak tersedia atau sudah kedaluwarsa. Gunakan /returnall lagi.", show_alert=True)
        await state.clear()
        return

    user = query.from_user
    try:
        client = await _connected_client(user.id)
        current = await client.list_numbers(page=1, per_page=1)
    except AugestelAccountNotConnected:
        await state.clear()
        await query.answer("Akun belum terhubung.", show_alert=True)
        await query.message.answer("Hubungkan ulang dengan /connect.")
        return
    except (SecretStorageError, AugestelIntegrationDisabled, AugestelIntegrationError) as exc:
        await state.clear()
        await query.answer("Tidak dapat memeriksa akun.", show_alert=True)
        await query.message.answer(f"Return All dihentikan: {escape(str(exc))}")
        return
    except Exception as exc:
        await state.clear()
        logger.error("Could not recheck Return All for Telegram user %s (%s)", user.id, type(exc).__name__)
        await query.answer("Tidak dapat memeriksa akun.", show_alert=True)
        await query.message.answer("Tidak ada request pengembalian yang dikirim.")
        return

    current_total = current["pagination"]["total"]
    if current_total == 0:
        await state.clear()
        await query.answer("Tidak ada nomor untuk dikembalikan.")
        await query.message.answer("Jumlah nomor sekarang 0. Return All tidak dijalankan.")
        return
    if current_total != data["expected_total"]:
        await state.set_data({"expected_total": current_total})
        await query.answer("Jumlah nomor berubah; periksa konfirmasi baru.", show_alert=True)
        await query.message.answer(
            f"Jumlah nomor berubah dari {data['expected_total']} menjadi {current_total}. "
            "Periksa kembali sebelum mengonfirmasi.",
            reply_markup=confirm_return_all(),
        )
        return

    # Clear FSM state before sending POST so repeated clicks cannot initiate a second request.
    await state.clear()
    await query.answer("Memproses Return All…")
    try:
        result = await client.return_all()
    except AugestelIntegrationDisabled as exc:
        await _audit(user.id, "return_all", "blocked_write_disabled", "No request was sent.")
        await query.message.answer(escape(str(exc)))
        return
    except AugestelOperationOutcomeUnknown:
        await _audit(
            user.id,
            "return_all",
            "outcome_unknown",
            "Write result unknown; do not retry until the live My Numbers count has been checked.",
        )
        await query.message.answer(
            "⚠️ Hasil Return All belum bisa dipastikan. Jangan jalankan ulang dulu. "
            "Periksa <code>/numbers</code> dan dashboard Augestel untuk memastikan jumlah nomor tersisa."
        )
        return
    except AugestelIntegrationError as exc:
        await _audit(
            user.id,
            "return_all",
            "failed",
            "Augestel did not provide a confirmed success response; no automatic retry was made.",
        )
        await query.message.answer(f"Return All gagal: {escape(str(exc))}")
        return
    except Exception as exc:
        logger.error("Unexpected Return All error for Telegram user %s (%s)", user.id, type(exc).__name__)
        await _audit(user.id, "return_all", "outcome_unknown", "Unexpected write error; check account before retry.")
        await query.message.answer(
            "Respons Return All tidak dapat dipastikan. Periksa <code>/numbers</code> sebelum mencoba lagi."
        )
        return

    await _audit(
        user.id,
        "return_all",
        "success",
        "Augestel returned success for Return All; verify the resulting number count with /numbers.",
    )
    await query.message.answer(
        "✅ Augestel mengembalikan status sukses untuk Return All. "
        "Jalankan <code>/numbers</code> untuk memverifikasi jumlah nomor yang tersisa."
    )


@router.callback_query(lambda query: query.data == "return_all:cancel")
async def cancel_return_all_callback(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await query.answer("Dibatalkan.")
    if query.from_user:
        await _audit(
            query.from_user.id,
            "return_all",
            "cancelled",
            "User cancelled before execution; no request was sent.",
        )
    if isinstance(query.message, Message):
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
