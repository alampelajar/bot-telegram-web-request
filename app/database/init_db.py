from app.database.base import Base
from app.database.session import get_engine
from app.models import OperationJob, User, WebsiteAccount  # noqa: F401


async def create_schema() -> None:
    """Create development schema; use Alembic migrations for managed production deployments."""
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
