from app.config import Settings


def test_admin_ids_parsing() -> None:
    settings = Settings(admin_telegram_ids="123, 456,invalid,,789")
    assert settings.admin_ids == {123, 456, 789}


def test_integration_disabled_by_default() -> None:
    settings = Settings()
    assert settings.augestel_integration_enabled is False
