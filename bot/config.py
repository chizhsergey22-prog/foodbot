from __future__ import annotations
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BOT_TOKEN: str
    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"
    MINI_APP_URL: str = "https://example.com"

    # Список telegram_id суперадминов через запятую
    SUPER_ADMIN_IDS: str = ""

    GOOGLE_CREDENTIALS_FILE: str = "/app/credentials.json"
    GOOGLE_DRIVE_FOLDER_ID: str = ""
    GOOGLE_REPORT_SHEET_ID: str = ""

    DEFAULT_CUTOFF_TIME: str = "17:00"
    TIMEZONE: str = "Europe/Kyiv"

    @property
    def super_admin_list(self) -> List[int]:
        if not self.SUPER_ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.SUPER_ADMIN_IDS.split(",") if x.strip()]


settings = Settings()
