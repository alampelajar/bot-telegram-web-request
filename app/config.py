from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr = Field(default=SecretStr(""))
    admin_telegram_ids: str = ""
    database_url: SecretStr = Field(
        default=SecretStr(
            "postgresql+asyncpg://awc:awc_dev_password@localhost:5432/automatic_web_controller"
        )
    )
    augestel_base_url: str = "https://augestel.com"
    # Set this only to the Base URL shown in Augestel's API documentation.
    augestel_api_base_url: str = ""
    augestel_api_key: SecretStr = Field(default=SecretStr(""))
    augestel_integration_enabled: bool = False
    app_env: str = "development"
    log_level: str = "INFO"
    export_tmp_dir: str = "./tmp/exports"
    export_retention_minutes: int = 30

    @property
    def admin_ids(self) -> set[int]:
        result: set[int] = set()
        for item in self.admin_telegram_ids.split(","):
            item = item.strip()
            if item.isdigit():
                result.add(int(item))
        return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
