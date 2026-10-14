from cryptography.fernet import Fernet
from pydantic import SecretStr
import pytest

import app.services.secret_store as secret_store
from app.config import Settings
from app.services.secret_store import SecretStorageError, decrypt_api_key, encrypt_api_key


def test_api_key_encryption_round_trip_and_ciphertext_is_not_plaintext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        api_key_encryption_key=SecretStr(Fernet.generate_key().decode("ascii")),
    )
    monkeypatch.setattr(secret_store, "get_settings", lambda: settings)
    api_key = "test-api-key-value-never-log"

    ciphertext = encrypt_api_key(api_key)

    assert ciphertext != api_key
    assert api_key not in ciphertext
    assert decrypt_api_key(ciphertext) == api_key


def test_encryption_fails_closed_without_master_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, api_key_encryption_key=SecretStr(""))
    monkeypatch.setattr(secret_store, "get_settings", lambda: settings)

    with pytest.raises(SecretStorageError, match="API_KEY_ENCRYPTION_KEY is not configured"):
        encrypt_api_key("test-api-key")


def test_invalid_encryption_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, api_key_encryption_key=SecretStr("not-a-fernet-key"))
    monkeypatch.setattr(secret_store, "get_settings", lambda: settings)

    with pytest.raises(SecretStorageError, match="API_KEY_ENCRYPTION_KEY is invalid"):
        encrypt_api_key("test-api-key")


def test_wrong_master_key_cannot_decrypt_ciphertext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Settings(
        _env_file=None,
        api_key_encryption_key=SecretStr(Fernet.generate_key().decode("ascii")),
    )
    encrypted = encrypt_api_key_with_settings(monkeypatch, original, "test-api-key")
    different = Settings(
        _env_file=None,
        api_key_encryption_key=SecretStr(Fernet.generate_key().decode("ascii")),
    )
    monkeypatch.setattr(secret_store, "get_settings", lambda: different)

    with pytest.raises(SecretStorageError, match="Could not decrypt"):
        decrypt_api_key(encrypted)


def encrypt_api_key_with_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    api_key: str,
) -> str:
    monkeypatch.setattr(secret_store, "get_settings", lambda: settings)
    return encrypt_api_key(api_key)
