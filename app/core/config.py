from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://vetglobal:vetglobal@localhost:5432/vetglobal"
    STORAGE_PATH: str = "./storage/uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
