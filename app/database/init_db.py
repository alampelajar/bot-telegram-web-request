from sqlalchemy import inspect, text

from app.database.base import Base
from app.database.session import get_engine
from app.models import OperationJob, User, WebsiteAccount  # noqa: F401


def _ensure_legacy_columns(connection) -> None:
    """Add columns introduced after the initial scaffold without deleting local data."""
    inspector = inspect(connection)
    dialect = connection.dialect.name
    datetime_type = "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME"

    column_additions = {
        "users": {
            "telegram_username": "VARCHAR(100)",
            "first_name": "VARCHAR(150)",
            "last_seen_at": datetime_type,
        },
        "website_accounts": {
            "updated_at": datetime_type,
        },
    }

    for table_name, columns in column_additions.items():
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, column_type in columns.items():
            if column_name not in existing:
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                )

    if "last_seen_at" in {col["name"] for col in inspect(connection).get_columns("users")}:
        connection.execute(
            text("UPDATE users SET last_seen_at = created_at WHERE last_seen_at IS NULL")
        )
    if "updated_at" in {
        col["name"] for col in inspect(connection).get_columns("website_accounts")
    }:
        connection.execute(
            text("UPDATE website_accounts SET updated_at = created_at WHERE updated_at IS NULL")
        )


async def create_schema() -> None:
    """Create missing tables and safely add fields to older local databases."""
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_legacy_columns)
