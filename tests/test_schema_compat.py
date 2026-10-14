from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
import pytest

from app.database.init_db import _ensure_legacy_columns


@pytest.mark.asyncio
async def test_legacy_sqlite_schema_gets_new_columns(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")

    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, telegram_id BIGINT UNIQUE, role VARCHAR(20), "
                "is_active BOOLEAN, created_at DATETIME)"
            )
        )
        await connection.execute(
            text(
                "CREATE TABLE website_accounts ("
                "id INTEGER PRIMARY KEY, user_id INTEGER, provider VARCHAR(40), "
                "connection_status VARCHAR(30), secret_reference VARCHAR(255), "
                "last_validated_at DATETIME, created_at DATETIME, notes TEXT)"
            )
        )
        await connection.execute(
            text("INSERT INTO users (id, telegram_id, role, is_active, created_at) "
                 "VALUES (1, 900001, 'user', 1, '2026-10-01 10:00:00')")
        )
        await connection.execute(
            text("INSERT INTO website_accounts "
                 "(id, user_id, provider, connection_status, created_at) "
                 "VALUES (1, 1, 'augestel', 'disconnected', '2026-10-01 10:00:00')")
        )
        await connection.run_sync(_ensure_legacy_columns)

        user_columns = {column["name"] for column in await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_columns("users")
        )}
        account_columns = {column["name"] for column in await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_columns("website_accounts")
        )}
        assert {"telegram_username", "first_name", "last_seen_at"} <= user_columns
        assert "updated_at" in account_columns

        user_time = await connection.execute(text("SELECT last_seen_at FROM users WHERE id=1"))
        account_time = await connection.execute(
            text("SELECT updated_at FROM website_accounts WHERE id=1")
        )
        assert user_time.scalar_one() is not None
        assert account_time.scalar_one() is not None

    await engine.dispose()
