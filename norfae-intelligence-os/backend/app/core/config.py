from pathlib import Path
import hmac
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):

    DATABASE_URL: str

    APP_ENV: Literal["development", "test", "production"] = "development"
    SHOPIFY_API_VERSION: str = Field(default="2026-04", pattern=r"^20\d{2}-(01|04|07|10)$")
    META_API_VERSION: str = Field(default="v27.0", pattern=r"^v\d{1,2}\.0$")
    JWT_SECRET_KEY: SecretStr | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=1440)

    OPENROUTER_API_KEY: SecretStr | None = None
    OPENROUTER_BASE_URL: AnyHttpUrl = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = Field(
        default="openai/gpt-4o-mini", min_length=1, max_length=200
    )
    OPENROUTER_TIMEOUT: float = Field(default=30.0, gt=0, le=300)
    OPENROUTER_MAX_RETRIES: int = Field(default=2, ge=0, le=5)
    ASSISTANT_TASK_TIMEOUT_SECONDS: float = Field(default=20.0, gt=0, le=120)
    ASSISTANT_REQUEST_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0, le=300)
    ASSISTANT_MAX_LLM_CALLS: int = Field(default=2, ge=1, le=4)
    ASSISTANT_MAX_TASK_ATTEMPTS: int = Field(default=16, ge=1, le=32)
    ASSISTANT_TASK_MAX_RETRIES: int = Field(default=1, ge=0, le=2)
    ASSISTANT_RETRY_BASE_SECONDS: float = Field(default=0.1, ge=0, le=1)
    ASSISTANT_RETRY_MAX_SECONDS: float = Field(default=0.5, gt=0, le=2)

    @field_validator("OPENROUTER_BASE_URL")
    @classmethod
    def require_secure_openrouter_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("OPENROUTER_BASE_URL must use HTTPS.")
        return value

    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def normalize_jwt_secret(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_jwt_configuration(self):
        jwt_secret = (
            self.JWT_SECRET_KEY.get_secret_value()
            if self.JWT_SECRET_KEY is not None
            else None
        )
        openrouter_secret = (
            self.OPENROUTER_API_KEY.get_secret_value()
            if self.OPENROUTER_API_KEY is not None
            else None
        )

        if jwt_secret and openrouter_secret and hmac.compare_digest(
            jwt_secret, openrouter_secret
        ):
            raise ValueError("JWT_SECRET_KEY must be different from OPENROUTER_API_KEY.")

        if self.JWT_ALGORITHM != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256.")

        if self.APP_ENV == "production":
            if jwt_secret is None or len(jwt_secret.encode("utf-8")) < 32:
                raise ValueError(
                    "Production requires a JWT_SECRET_KEY of at least 32 bytes."
                )
            normalized = jwt_secret.lower()
            if (
                len(set(jwt_secret)) < 8
                or normalized.startswith(
                    ("change", "replace", "example", "your-", "dev-only", "test-")
                )
            ):
                raise ValueError("Production JWT_SECRET_KEY is insecure or a placeholder.")

        return self

    # ===================================
    # DISCORD
    # ===================================

    DISCORD_BOT_TOKEN: str | None = None

    # ===================================
    # META
    # ===================================

    META_SYNC_INTERVAL: int = 300

    # ===================================
    # TAXES
    # ===================================

    GST_PERCENTAGE: int = 16
    FUEL_SURCHARGE_PERCENTAGE: int = 30
    INCOME_TAX_PERCENTAGE: int = 4

    # ===================================
    # PACKAGING
    # ===================================

    DEFAULT_PACKAGING_COST: int = 50

    # ===================================
    # WAREHOUSE
    # ===================================

    WAREHOUSE_CITY: str = "Lahore"
    WAREHOUSE_PROVINCE: str = "Punjab"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="allow",
    )


settings = Settings()
