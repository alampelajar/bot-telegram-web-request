from app.config import Settings


def test_admin_ids_parsing() -> None:
    settings = Settings(admin_telegram_ids="123, 456,invalid,,789")
    assert settings.admin_ids == {123, 456, 789}


def test_integration_disabled_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.augestel_integration_enabled is False


def test_documented_augestel_api_base_url_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.augestel_api_base_url == "https://augestel.com/api/v1/iprn"


def test_api_key_is_empty_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.augestel_api_key.get_secret_value() == ""
