"""Encryption helpers for user-supplied Augestel API keys.

Only ciphertext belongs in the database. The Fernet master key is configured
out-of-band in API_KEY_ENCRYPTION_KEY and must not be committed or sent to chat.
"""
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class SecretStorageError(RuntimeError):
    """Raised when API-key encryption/decryption cannot be safely completed."""


def _fernet() -> Fernet:
    raw_key = get_settings().api_key_encryption_key.get_secret_value().strip()
    if not raw_key:
        raise SecretStorageError(
            "API_KEY_ENCRYPTION_KEY is not configured in the environment."
        )
    try:
        return Fernet(raw_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise SecretStorageError(
            "API_KEY_ENCRYPTION_KEY is invalid; generate a Fernet key and keep it private."
        ) from exc


def encrypt_api_key(api_key: str) -> str:
    if not api_key or api_key.isspace():
        raise SecretStorageError("The API key is empty.")
    try:
        return _fernet().encrypt(api_key.encode("utf-8")).decode("ascii")
    except (ValueError, UnicodeEncodeError) as exc:
        raise SecretStorageError("Could not encrypt the API key.") from exc


def decrypt_api_key(ciphertext: str) -> str:
    if not ciphertext:
        raise SecretStorageError("No encrypted API key is stored.")
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeEncodeError, UnicodeDecodeError) as exc:
        raise SecretStorageError(
            "Could not decrypt the stored API key; check API_KEY_ENCRYPTION_KEY."
        ) from exc
