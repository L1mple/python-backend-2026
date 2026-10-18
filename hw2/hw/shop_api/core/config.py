from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "Shop API"
    app_description: str = (
        "Апи магазина"
    )
    database_url: str = "sqlite+aiosqlite:///./shop.db"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
