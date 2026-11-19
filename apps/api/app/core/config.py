"""Application configuration managed via environment variables and Pydantic settings."""

from functools import lru_cache
import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_CANDIDATE_DIRS = list(dict.fromkeys([*reversed(Path(__file__).resolve().parents[:5]), Path.cwd()]))
_ENV_FILES = tuple(
    str(directory / filename)
    for directory in _CANDIDATE_DIRS
    for filename in (".env", ".env.local")
    if (directory / filename).is_file()
)


class Settings(BaseSettings):
    """Runtime settings for Leaders Document Intelligence."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Leaders Document Intelligence"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api"

    # Security & JWT
    SECRET_KEY: str = Field(
        default="ldi-dev-secret-key-please-override-in-production-64chars-min-0001"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SIGNED_URL_SECRET: str = Field(
        default="ldi-dev-signed-url-secret-please-override-in-production-64chars"
    )
    SIGNED_URL_TTL_SECONDS: int = 300
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    ENCRYPTION_KEY: str = ""

    # CORS
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> list[str]:
        """Accept either a JSON array or comma-separated origin URLs, stripping trailing slashes."""
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                parsed = json.loads(raw)
                items = [str(item).strip() for item in parsed]
            else:
                items = [item.strip() for item in raw.split(",")]
        elif isinstance(value, (list, tuple, set)):
            items = [str(item).strip() for item in value]
        else:
            raise ValueError("CORS_ORIGINS must be a list or comma-separated string of URLs")
        return [item.rstrip("/") for item in items if item]

    @field_validator("STORAGE_BACKEND", mode="before")
    @classmethod
    def _normalize_storage_backend(cls, value: Any) -> Any:
        """Normalize storage backend strings (e.g. 'R2' -> 'r2', 'S3' -> 's3')."""
        return value.strip().lower() if isinstance(value, str) else value

    # Database (PostgreSQL primary, SQLite fallback when running standalone locally)
    DATABASE_URL: str = "sqlite:///../ldi_private_vault/ldi_local.db"
    DATABASE_URL_UNPOOLED: str = ""

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_ALWAYS_EAGER: bool = False

    # Object Storage (S3, Cloudflare R2, MinIO, Neon Object Storage AWS_* vars, or local vault)
    STORAGE_BACKEND: Literal["s3", "r2", "minio", "local_vault"] = "local_vault"
    LOCAL_VAULT_PATH: str = "../ldi_private_vault/storage"
    S3_BUCKET_NAME: str = "ldi-documents-private"
    NEON_STORAGE_BUCKET: str = "assets"
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_USE_SSL: bool = True
    S3_FORCE_PATH_STYLE: bool = False

    # Neon Object Storage compatibility environment variables (pulled by `neon deploy`)
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_ENDPOINT_URL_S3: str | None = None
    AWS_REGION: str = "us-east-2"

    @model_validator(mode="after")
    def _map_neon_env_defaults(self) -> "Settings":
        """Map Neon `neon deploy` AWS_* object storage variables when explicit S3_* vars are omitted."""
        if not self.S3_ACCESS_KEY_ID and self.AWS_ACCESS_KEY_ID:
            self.S3_ACCESS_KEY_ID = self.AWS_ACCESS_KEY_ID
        if not self.S3_SECRET_ACCESS_KEY and self.AWS_SECRET_ACCESS_KEY:
            self.S3_SECRET_ACCESS_KEY = self.AWS_SECRET_ACCESS_KEY
        if not self.S3_ENDPOINT_URL and self.AWS_ENDPOINT_URL_S3:
            self.S3_ENDPOINT_URL = self.AWS_ENDPOINT_URL_S3
        if "S3_REGION" not in self.model_fields_set and "AWS_REGION" in self.model_fields_set:
            self.S3_REGION = self.AWS_REGION
        if (
            "S3_BUCKET_NAME" not in self.model_fields_set
            and self.S3_ENDPOINT_URL
            and "neon.tech" in self.S3_ENDPOINT_URL
        ):
            self.S3_BUCKET_NAME = self.NEON_STORAGE_BUCKET
        if not self.S3_FORCE_PATH_STYLE and self.S3_ENDPOINT_URL and "neon.tech" in self.S3_ENDPOINT_URL:
            self.S3_FORCE_PATH_STYLE = True
        if (
            "STORAGE_BACKEND" not in self.model_fields_set
            and self.S3_ACCESS_KEY_ID
            and self.S3_ENDPOINT_URL
        ):
            self.STORAGE_BACKEND = "s3"
        return self

    # AI Provider
    AI_PROVIDER: Literal["GEMINI", "OPENAI", "LOCAL_DETERMINISTIC"] = "LOCAL_DETERMINISTIC"
    ALLOW_EXTERNAL_AI: bool = False
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    REDACT_PII_BEFORE_EXTERNAL_AI: bool = True

    # OCR Provider
    OCR_PROVIDER: Literal[
        "TESSERACT", "GOOGLE_DOC_AI", "AZURE_DOC_INTELLIGENCE", "LOCAL_FALLBACK"
    ] = "TESSERACT"
    GOOGLE_DOC_AI_ENDPOINT: str = ""
    GOOGLE_DOC_AI_API_KEY: str = ""
    AZURE_DOC_INTELLIGENCE_ENDPOINT: str = ""
    AZURE_DOC_INTELLIGENCE_KEY: str = ""

    # Upload & Security limits
    MAX_UPLOAD_FILE_SIZE_MB: int = 25
    MAX_BATCH_FILES: int = 50
    MAX_ZIP_EXTRACT_FILES: int = 60
    MAX_ZIP_EXTRACT_SIZE_MB: int = 150
    MAX_ZIP_COMPRESSION_RATIO: int = 50
    CLAMAV_HOST: str = ""
    CLAMAV_PORT: int = 3310

    # Retention
    DEFAULT_RETENTION_DAYS: int = 365

    @property
    def resolved_vault_path(self) -> Path:
        """Resolve local vault path outside the source code directory."""
        base = Path(__file__).resolve().parents[3]  # workspace root or parent
        candidate = Path(self.LOCAL_VAULT_PATH)
        if candidate.is_absolute():
            path = candidate
        else:
            # Resolve relative to api dir, ensuring it sits outside app source
            api_dir = Path(__file__).resolve().parents[2]
            path = (api_dir / candidate).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _normalize_db_url(self, raw_url: str) -> str:
        """Normalize Postgres schemes for psycopg3 and ensure SQLite parent dir exists."""
        url = raw_url.strip()
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("sqlite:///"):
            rel_or_abs = url.replace("sqlite:///", "", 1)
            db_path = Path(rel_or_abs)
            if not db_path.is_absolute():
                api_dir = Path(__file__).resolve().parents[2]
                db_path = (api_dir / db_path).resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{db_path.as_posix()}"
        return url

    @property
    def effective_database_url(self) -> str:
        """Pooled/runtime SQLAlchemy database URL."""
        return self._normalize_db_url(self.DATABASE_URL)

    @property
    def unpooled_database_url(self) -> str:
        """Direct unpooled connection URL for Alembic DDL migrations when provided."""
        return self._normalize_db_url(self.DATABASE_URL_UNPOOLED or self.DATABASE_URL)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()


settings = get_settings()
