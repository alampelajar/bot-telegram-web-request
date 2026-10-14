from app.bot.handlers.operations import _format_number_page
from app.bot.keyboards import numbers_pagination


def test_number_page_formats_rate_and_escapes_provider_text() -> None:
    payload = {
        "success": True,
        "data": [
            {
                "number": "+12025551234",
                "range_name": "US <Premium>",
                "a2p_rate": 0.015,
                "portal_limit_a2p": 100,
                "last_message_at": "2025-01-15T10:30:00Z",
                "assigned_at": "2025-01-10T08:00:00Z",
            }
        ],
        "pagination": {
            "current_page": 1,
            "per_page": 20,
            "total": 21,
            "last_page": 2,
        },
    }

    text, keyboard = _format_number_page(payload)

    assert "+12025551234" in text
    assert "US &lt;Premium&gt;" in text
    assert "0.0150" in text
    assert "Portal limit" in text
    assert keyboard is not None
    assert keyboard.inline_keyboard[0][0].callback_data == "numbers:page:2"


def test_last_number_page_has_previous_button_only() -> None:
    keyboard = numbers_pagination(page=2, last_page=2)

    assert keyboard is not None
    assert keyboard.inline_keyboard[0][0].text == "⬅️ Previous"
    assert keyboard.inline_keyboard[0][0].callback_data == "numbers:page:1"


def test_single_page_has_no_pagination_keyboard() -> None:
    assert numbers_pagination(page=1, last_page=1) is None
