from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "production-base"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://app:change-me@localhost:5432/app_db"
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
