from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "Shop API"
    app_description: str = (
        "Апи магазина"
    )
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/shop_db"
    )

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
