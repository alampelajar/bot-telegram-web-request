from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import pytest

from app.database.base import Base
from app.models import OperationJob, User, WebsiteAccount  # noqa: F401
from app.services import accounts as account_service


@pytest.mark.asyncio
async def test_user_registration_and_account_status_lifecycle(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "test_accounts.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(account_service, "create_session_factory", lambda: factory)
    try:
        initial = await account_service.get_account_status(telegram_id=700001)
        assert initial.connection_status == "not_registered"

        user_id = await account_service.register_or_touch_user(
            telegram_id=700001,
            username="tester",
            first_name="Test User",
        )
        same_user_id = await account_service.register_or_touch_user(
            telegram_id=700001,
            username="tester_updated",
            first_name="Test User",
        )
        assert same_user_id == user_id

        before_connect = await account_service.get_account_status(telegram_id=700001)
        assert before_connect.connection_status == "not_connected"

        pending = await account_service.set_connection_pending(user_id)
        assert pending.connection_status == "auth_method_required"

        stored = await account_service.get_account_status(telegram_id=700001)
        assert stored.connection_status == "auth_method_required"
        assert stored.provider == "augestel"

        assert await account_service.disconnect_account(telegram_id=700001) is True
        disconnected = await account_service.get_account_status(telegram_id=700001)
        assert disconnected.connection_status == "disconnected"
    finally:
        await engine.dispose()
