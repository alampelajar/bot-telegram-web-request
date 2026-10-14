from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery

from app.bot.handlers.operations import confirm_return_all_callback, cancel_return_all_callback


@pytest.mark.asyncio
async def test_return_all_confirmation_does_not_send_request() -> None:
    message = MagicMock()
    message.answer = AsyncMock()
    query = MagicMock(spec=CallbackQuery)
    query.data = "return_all:confirm"
    query.from_user = MagicMock(id=700001)
    query.message = message
    query.answer = AsyncMock()

    await confirm_return_all_callback(query)

    query.answer.assert_awaited_once()
    message.answer.assert_awaited_once()
    assert "tidak dijalankan" in message.answer.await_args.args[0].lower()


@pytest.mark.asyncio
async def test_return_all_cancel_does_not_send_request() -> None:
    message = MagicMock()
    message.answer = AsyncMock()
    query = MagicMock(spec=CallbackQuery)
    query.data = "return_all:cancel"
    query.from_user = MagicMock(id=700001)
    query.message = message
    query.answer = AsyncMock()

    await cancel_return_all_callback(query)

    query.answer.assert_awaited_once()
    message.answer.assert_awaited_once()
    assert "dibatalkan" in message.answer.await_args.args[0].lower()
