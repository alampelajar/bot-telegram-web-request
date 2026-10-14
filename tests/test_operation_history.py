from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import pytest

from app.database.base import Base
from app.models import OperationJob, User, WebsiteAccount  # noqa: F401
from app.services import operation_history


@pytest.mark.asyncio
async def test_operation_history_is_scoped_to_telegram_user(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "test_history.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    from app.services import accounts

    monkeypatch.setattr(accounts, "create_session_factory", lambda: factory)
    monkeypatch.setattr(operation_history, "create_session_factory", lambda: factory)
    try:
        await accounts.register_or_touch_user(telegram_id=111001, username="one", first_name="One")
        await accounts.register_or_touch_user(telegram_id=222002, username="two", first_name="Two")

        assert await operation_history.record_operation(
            111001,
            "download_numbers",
            "blocked_integration_disabled",
            result_summary="No request sent.",
        )
        assert await operation_history.record_operation(
            222002,
            "add_number",
            "blocked_integration_disabled",
            result_summary="No request sent.",
        )

        one_records = await operation_history.list_operations(111001)
        two_records = await operation_history.list_operations(222002)
        assert len(one_records) == 1
        assert one_records[0].operation_type == "download_numbers"
        assert len(two_records) == 1
        assert two_records[0].operation_type == "add_number"
        assert await operation_history.list_operations(333003) == []
    finally:
        await engine.dispose()
