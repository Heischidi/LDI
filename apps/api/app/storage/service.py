"""S3-compatible (AWS S3, Cloudflare R2, MinIO) and private Local Vault storage backends."""

from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.security import generate_signed_token


class StorageBackend(ABC):
    """Abstract storage interface ensuring private buckets and immutable originals."""

    @abstractmethod
    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Persist bytes under the private object key."""

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        """Read bytes for the given private object key."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check whether key exists."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete object key (never used on originals except retention purge)."""

    @abstractmethod
    def generate_download_url(self, key: str, ttl_seconds: int | None = None) -> str:
        """Generate a short-lived signed download URL without exposing public bucket URLs."""


class LocalVaultStorageBackend(StorageBackend):
    """Private filesystem storage stored outside application source code."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or settings.resolved_vault_path).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        clean_key = key.lstrip("/").replace("\\", "/")
        candidate = (self.root_dir / clean_key).resolve()
        if self.root_dir not in candidate.parents and candidate != self.root_dir:
            raise ValueError("Invalid storage key path traversal detected.")
        return candidate

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        target = self._safe_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return key

    def get_bytes(self, key: str) -> bytes:
        target = self._safe_path(key)
        if not target.exists():
            raise FileNotFoundError(f"Stored object not found: {key}")
        return target.read_bytes()

    def exists(self, key: str) -> bool:
        return self._safe_path(key).exists()

    def delete(self, key: str) -> None:
        target = self._safe_path(key)
        if target.exists():
            target.unlink()

    def generate_download_url(self, key: str, ttl_seconds: int | None = None) -> str:
        sig, exp = generate_signed_token(key, ttl_seconds=ttl_seconds)
        return f"{settings.API_V1_PREFIX}/exports/signed-object?key={key}&sig={sig}&exp={exp}"


class S3StorageBackend(StorageBackend):
    """S3-compatible storage supporting AWS S3, Cloudflare R2, and MinIO."""

    def __init__(self) -> None:
        self.bucket = settings.S3_BUCKET_NAME
        boto_cfg_kwargs: dict = {
            "signature_version": "s3v4",
            "connect_timeout": 10,
            "read_timeout": 30,
            "retries": {"max_attempts": 2},
        }
        if settings.S3_FORCE_PATH_STYLE or settings.S3_ENDPOINT_URL:
            boto_cfg_kwargs["s3"] = {"addressing_style": "path"}
        self.client = boto3.client(
            "s3",
            region_name=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            use_ssl=settings.S3_USE_SSL,
            config=BotoConfig(**boto_cfg_kwargs),
        )
        self._ensure_private_bucket()

    def _ensure_private_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except ClientError:
                pass

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        put_kwargs: dict = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
        }
        if settings.STORAGE_BACKEND == "s3" and not settings.S3_ENDPOINT_URL:
            put_kwargs["ServerSideEncryption"] = "AES256"
        self.client.put_object(**put_kwargs)
        return key

    def get_bytes(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def generate_download_url(self, key: str, ttl_seconds: int | None = None) -> str:
        ttl = ttl_seconds or settings.SIGNED_URL_TTL_SECONDS
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=ttl,
        )


@lru_cache(maxsize=4)
def _get_cached_s3_backend(
    backend_name: str,
    bucket_name: str,
    endpoint_url: str | None,
    access_key_id: str | None,
    secret_access_key: str | None,
    region_name: str,
    use_ssl: bool,
    force_path_style: bool,
) -> S3StorageBackend:
    """Reuse initialized boto3 S3 client & bucket check across requests for the same config."""
    return S3StorageBackend()


def get_storage_backend() -> StorageBackend:
    """Instantiate or reuse configured storage backend."""
    if settings.STORAGE_BACKEND in {"s3", "r2", "minio"} and settings.S3_ACCESS_KEY_ID:
        return _get_cached_s3_backend(
            settings.STORAGE_BACKEND,
            settings.S3_BUCKET_NAME,
            settings.S3_ENDPOINT_URL,
            settings.S3_ACCESS_KEY_ID,
            settings.S3_SECRET_ACCESS_KEY,
            settings.S3_REGION,
            settings.S3_USE_SSL,
            settings.S3_FORCE_PATH_STYLE,
        )
    return LocalVaultStorageBackend()
