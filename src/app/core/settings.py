from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = ""
    db_pool_size: int = 50
    db_max_overflow: int = 30
    db_pool_timeout: int = 5
    db_pool_recycle: int = 1800

    debug: bool = False
    testing: bool = False
    title: str = "Warehouse Management API"
    version: str = "1.0.0"
    description: str = "A FastAPI application for warehouse management"

    host: str = "0.0.0.0"
    port: int = 8000

    rate_limit_per_minute: int = 300
    secret_key: str = "your-secret-key-here"
    api_key_header: str = "X-API-Key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_minutes: int = 7 * 24 * 60

    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL environment variable is required")
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "your-secret-key-here":
            import warnings

            warnings.warn(
                "Using default secret key! Set SECRET_KEY environment variable in production.",
                UserWarning,
            )
        return v

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return v

    model_config = ConfigDict(
        env_file=(".env", "../.env"),
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
