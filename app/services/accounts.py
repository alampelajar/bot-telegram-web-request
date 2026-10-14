from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import SecretStr
from sqlalchemy import select

from app.database.session import create_session_factory
from app.models.user import User
from app.models.website_account import WebsiteAccount
from app.services.secret_store import decrypt_api_key


@dataclass(frozen=True)
class AccountStatus:
    connection_status: str
    provider: str = "augestel"
    last_validated_at: datetime | None = None
    has_api_key: bool = False


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
    """Legacy status helper retained for compatibility; does not store credentials."""
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
                notes="Waiting for the user to connect with an Augestel API key.",
            )
            session.add(account)
        elif account.connection_status != "connected":
            account.connection_status = "auth_method_required"
            account.notes = "Waiting for the user to connect with an Augestel API key."
        await session.commit()
        return AccountStatus(
            connection_status=account.connection_status,
            provider=account.provider,
            last_validated_at=account.last_validated_at,
            has_api_key=bool(account.api_key_encrypted),
        )


async def save_api_key_for_user(telegram_id: int, encrypted_api_key: str) -> AccountStatus:
    """Save only an already-encrypted key after the caller has validated it with Augestel."""
    factory = create_session_factory()
    async with factory() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, last_seen_at=datetime.now(timezone.utc))
            session.add(user)
            await session.flush()

        result = await session.execute(
            select(WebsiteAccount).where(
                WebsiteAccount.user_id == user.id,
                WebsiteAccount.provider == "augestel",
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            account = WebsiteAccount(user_id=user.id, provider="augestel")
            session.add(account)

        now = datetime.now(timezone.utc)
        account.api_key_encrypted = encrypted_api_key
        account.connection_status = "connected"
        account.last_validated_at = now
        account.notes = "API key validated against the documented read-only My Numbers endpoint."
        await session.commit()
        return AccountStatus(
            connection_status=account.connection_status,
            provider=account.provider,
            last_validated_at=account.last_validated_at,
            has_api_key=True,
        )


async def load_api_key_for_user(telegram_id: int) -> SecretStr | None:
    """Return a user's API key wrapped as SecretStr, decrypted only when needed."""
    factory = create_session_factory()
    async with factory() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if user is None:
            return None
        result = await session.execute(
            select(WebsiteAccount).where(
                WebsiteAccount.user_id == user.id,
                WebsiteAccount.provider == "augestel",
            )
        )
        account = result.scalar_one_or_none()
        if account is None or not account.api_key_encrypted or account.connection_status != "connected":
            return None
        plaintext = decrypt_api_key(account.api_key_encrypted)
        return SecretStr(plaintext)


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
            has_api_key=bool(account.api_key_encrypted),
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
        account.api_key_encrypted = None
        account.last_validated_at = None
        account.notes = None
        await session.commit()
        return True
