from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BOT_TOKEN: str
    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"
    TIMEZONE: str = "Europe/Kyiv"


settings = Settings()
