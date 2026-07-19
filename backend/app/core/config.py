import secrets
import warnings
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    APP_EDITION: str = "suite"
    BUILD_MANIFEST_PATH: Path | None = None

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None
    REDIS_URL: str | None = None
    REDIS_KEY_PREFIX: str = "fast-vben-admin"
    REDIS_CACHE_TTL_SECONDS: int = 300
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 1.0
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 1.0
    LOGIN_RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300
    LOGIN_RATE_LIMIT_BLOCK_SECONDS: int = 900
    LOGIN_CAPTCHA_ENABLED: bool = True
    LOGIN_CAPTCHA_THRESHOLD: int = 3
    LOGIN_CAPTCHA_TTL_SECONDS: int = 300
    LOGIN_SLIDER_CAPTCHA_ENABLED: bool = True
    LOGIN_SLIDER_CAPTCHA_TTL_SECONDS: int = 180
    SMS_CODE_TTL_SECONDS: int = 300
    SMS_CODE_RESEND_SECONDS: int = 60
    SMS_CODE_MAX_ATTEMPTS: int = 5
    SMS_CODE_SEND_MAX_PER_IP: int = 10
    QR_CODE_LOGIN_TTL_SECONDS: int = 180
    MFA_TOTP_ENABLED: bool = True
    MFA_TOTP_ISSUER: str = "Fast Vben Admin"
    MFA_TOTP_VALID_WINDOW: int = 1
    ENTERPRISE_OIDC_ENABLED: bool = False
    ENTERPRISE_OIDC_ISSUER: str | None = None
    ENTERPRISE_OIDC_DISCOVERY_URL: str | None = None
    ENTERPRISE_OIDC_CLIENT_ID: str | None = None
    ENTERPRISE_OIDC_CLIENT_SECRET: str | None = None
    ENTERPRISE_OIDC_REDIRECT_URI: str | None = None
    ENTERPRISE_OIDC_FRONTEND_LOGIN_URL: str | None = None
    ENTERPRISE_OIDC_SCOPES: str = "openid email profile"
    ENTERPRISE_OIDC_ROLE_CLAIM: str = "groups"
    ENTERPRISE_OIDC_ROLE_MAPPING: str = "{}"
    ENTERPRISE_OIDC_ROLE_SYNC_MODE: Literal["disabled", "replace"] = "disabled"
    ENTERPRISE_OIDC_ACTIVE_CLAIM: str = "active"
    ENTERPRISE_OIDC_SYNC_ACTIVE_STATUS: bool = False
    ENTERPRISE_OIDC_REQUIRE_VERIFIED_EMAIL: bool = True
    ENTERPRISE_OIDC_STATE_TTL_SECONDS: int = 300
    ENTERPRISE_OIDC_TICKET_TTL_SECONDS: int = 60
    ENTERPRISE_OIDC_HTTP_TIMEOUT_SECONDS: float = 5.0
    METRICS_ENABLED: bool = True
    METRICS_AUTH_TOKEN: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str
    UPLOAD_DIR: str = "uploads"
    UPLOAD_MAX_SIZE_MB: int = 10
    UPLOAD_ALLOWED_EXTENSIONS: str = (
        "jpg,jpeg,png,gif,webp,pdf,doc,docx,xls,xlsx,csv,txt,zip"
    )
    STORAGE_PROVIDER: Literal["local", "s3"] = "local"
    S3_ENDPOINT_URL: str | None = None
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_OBJECT_PREFIX: str = "uploads"
    S3_ADDRESSING_STYLE: Literal["auto", "path", "virtual"] = "auto"
    S3_AUTO_CREATE_BUCKET: bool = False
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 300

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore
