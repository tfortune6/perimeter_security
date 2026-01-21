from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 同步 DSN（SQLModel/SQLAlchemy sync engine）
    DATABASE_URL: str = "postgresql+psycopg://postgres:123456@localhost:5432/perimeter_security"

    # 上传目录（相对项目根目录 backend/）
    UPLOAD_DIR: str = "static/uploads"


settings = Settings()
