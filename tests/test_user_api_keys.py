from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import pytest

import app.services.secret_store as secret_store
from app.config import Settings
from app.database.base import Base
from app.models import OperationJob, User, WebsiteAccount  # noqa: F401
from app.services import accounts as account_service
from app.services.secret_store import encrypt_api_key


@pytest.mark.asyncio
async def test_api_key_is_encrypted_scoped_to_telegram_user_and_removed_on_disconnect(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'user_keys.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        api_key_encryption_key=SecretStr(Fernet.generate_key().decode("ascii")),
    )
    monkeypatch.setattr(secret_store, "get_settings", lambda: settings)
    monkeypatch.setattr(account_service, "create_session_factory", lambda: factory)

    key_for_user_a = "user-a-api-key-test-value"
    try:
        await account_service.register_or_touch_user(700001, "user_a", "User A")
        await account_service.register_or_touch_user(700002, "user_b", "User B")

        ciphertext = encrypt_api_key(key_for_user_a)
        saved = await account_service.save_api_key_for_user(700001, ciphertext)

        assert saved.connection_status == "connected"
        assert saved.has_api_key is True

        loaded_a = await account_service.load_api_key_for_user(700001)
        loaded_b = await account_service.load_api_key_for_user(700002)
        assert loaded_a is not None
        assert loaded_a.get_secret_value() == key_for_user_a
        assert loaded_b is None

        async with factory() as session:
            row = await session.scalar(
                select(WebsiteAccount).join(User).where(User.telegram_id == 700001)
            )
            assert row is not None
            assert row.api_key_encrypted == ciphertext
            assert key_for_user_a not in row.api_key_encrypted

        assert await account_service.disconnect_account(700001) is True
        assert await account_service.load_api_key_for_user(700001) is None
    finally:
        await engine.dispose()
