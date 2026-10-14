from app.database.base import Base
from app.database.session import create_session_factory
from app.models import OperationJob, User, WebsiteAccount


async def create_schema() -> None:
    """Create schema for local development. Use Alembic migrations in production."""
    session_factory = create_session_factory()
    engine = session_factory.kw["bind"]
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
