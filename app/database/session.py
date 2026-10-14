from functools import lru_cache
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    database_url = get_settings().database_url.get_secret_value()
    parsed_url = make_url(database_url)

    # Ensure parent directory exists for local SQLite development.
    if parsed_url.drivername.startswith("sqlite") and parsed_url.database not in (None, "", ":memory:"):
        Path(parsed_url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    return create_async_engine(database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def create_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def close_database() -> None:
    engine = get_engine()
    await engine.dispose()
    get_engine.cache_clear()
    create_session_factory.cache_clear()
