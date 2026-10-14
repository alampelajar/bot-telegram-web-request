from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.operations import confirm_return_all_callback, cancel_return_all_callback


@pytest.mark.asyncio
async def test_return_all_confirmation_without_pending_state_is_rejected() -> None:
    message = MagicMock(spec=Message)
    message.chat = MagicMock()
    message.chat.type = ChatType.PRIVATE
    message.answer = AsyncMock()

    query = MagicMock(spec=CallbackQuery)
    query.data = "return_all:confirm"
    query.from_user = MagicMock(id=700001)
    query.message = message
    query.answer = AsyncMock()

    state = MagicMock()
    state.get_state = AsyncMock(return_value=None)
    state.get_data = AsyncMock(return_value={})
    state.clear = AsyncMock()

    await confirm_return_all_callback(query, state)

    query.answer.assert_awaited_once()
    state.clear.assert_awaited_once()
    # No write call can occur without a live confirmation state.
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_return_all_cancel_clears_state_without_request() -> None:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()

    query = MagicMock(spec=CallbackQuery)
    query.data = "return_all:cancel"
    query.from_user = MagicMock(id=700001)
    query.message = message
    query.answer = AsyncMock()

    state = MagicMock()
    state.clear = AsyncMock()

    await cancel_return_all_callback(query, state)

    query.answer.assert_awaited_once()
    state.clear.assert_awaited_once()
    message.answer.assert_awaited_once()
    assert "dibatalkan" in message.answer.await_args.args[0].lower()
