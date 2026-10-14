from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from app.database.session import create_session_factory
from app.models.user import User
from app.models.website_account import WebsiteAccount


@dataclass(frozen=True)
class AccountStatus:
    connection_status: str
    provider: str = "augestel"
    last_validated_at: datetime | None = None


async def register_or_touch_user(
    telegram_id: int,
    username: str | None,
    first_name: str | None,
) -> int:
    factory = create_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                telegram_username=username,
                first_name=first_name,
                last_seen_at=now,
            )
            session.add(user)
            await session.flush()
        else:
            user.telegram_username = username
            user.first_name = first_name
            user.last_seen_at = now
        await session.commit()
        return user.id


async def set_connection_pending(user_id: int) -> AccountStatus:
    factory = create_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(WebsiteAccount).where(
                WebsiteAccount.user_id == user_id,
                WebsiteAccount.provider == "augestel",
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            account = WebsiteAccount(
                user_id=user_id,
                provider="augestel",
                connection_status="auth_method_required",
                notes="Awaiting an approved Augestel authentication method.",
            )
            session.add(account)
        elif account.connection_status != "connected":
            account.connection_status = "auth_method_required"
            account.notes = "Awaiting an approved Augestel authentication method."
        await session.commit()
        return AccountStatus(
            connection_status=account.connection_status,
            provider=account.provider,
            last_validated_at=account.last_validated_at,
        )


async def get_account_status(telegram_id: int) -> AccountStatus:
    factory = create_session_factory()
    async with factory() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if user is None:
            return AccountStatus(connection_status="not_registered")

        result = await session.execute(
            select(WebsiteAccount).where(
                WebsiteAccount.user_id == user.id,
                WebsiteAccount.provider == "augestel",
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            return AccountStatus(connection_status="not_connected")
        return AccountStatus(
            connection_status=account.connection_status,
            provider=account.provider,
            last_validated_at=account.last_validated_at,
        )


async def disconnect_account(telegram_id: int) -> bool:
    factory = create_session_factory()
    async with factory() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if user is None:
            return False
        result = await session.execute(
            select(WebsiteAccount).where(
                WebsiteAccount.user_id == user.id,
                WebsiteAccount.provider == "augestel",
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            return False
        account.connection_status = "disconnected"
        account.secret_reference = None
        account.last_validated_at = None
        account.notes = None
        await session.commit()
        return True
