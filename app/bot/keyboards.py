from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Add Number", callback_data="menu:add"),
                InlineKeyboardButton(text="📥 Download Numbers", callback_data="menu:download"),
            ],
            [InlineKeyboardButton(text="📱 My Numbers", callback_data="menu:numbers")],
            [InlineKeyboardButton(text="↩️ Return All", callback_data="menu:return_all")],
            [
                InlineKeyboardButton(text="🔗 Connect Account", callback_data="menu:connect"),
                InlineKeyboardButton(text="👤 My Account", callback_data="menu:account"),
            ],
            [InlineKeyboardButton(text="🧾 Operation History", callback_data="menu:history")],
        ]
    )


def numbers_pagination(page: int, last_page: int) -> InlineKeyboardMarkup | None:
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️ Previous",
                callback_data=f"numbers:page:{page - 1}",
            )
        )
    if page < last_page:
        buttons.append(
            InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"numbers:page:{page + 1}",
            )
        )
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def confirm_return_all() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ I Confirm Return All", callback_data="return_all:confirm"),
                InlineKeyboardButton(text="Cancel", callback_data="return_all:cancel"),
            ]
        ]
    )
