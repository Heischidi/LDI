"""Security primitives: bcrypt hashing, JWT access/refresh tokens, signed URLs, and PII sanitization."""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import settings

# In-memory token revocation store (backed by Redis when available)
_REVOKED_JTIS: set[str] = set()


def compute_base_username(first_name: str, last_name: str) -> str:
    """Build deterministic login username: lastname + first two letters of firstname."""
    clean_last = re.sub(r"[^a-z0-9]", "", last_name.strip().lower())
    clean_first = re.sub(r"[^a-z0-9]", "", first_name.strip().lower())
    prefix = clean_last or "officer"
    suffix = clean_first[:2] or "ld"
    return f"{prefix}{suffix}"


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    jti = secrets.token_urlsafe(16)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "type": "access",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str, role: str) -> str:
    """Create a signed JWT refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    jti = secrets.token_urlsafe(16)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token, checking revocation list."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        raise JWTError("Token has been revoked")
    return payload


def revoke_token(jti: str) -> None:
    """Mark a JWT ID as revoked."""
    _REVOKED_JTIS.add(jti)


def is_token_revoked(jti: str) -> bool:
    """Check whether a JWT ID has been revoked."""
    return jti in _REVOKED_JTIS


def generate_signed_token(resource_key: str, ttl_seconds: int | None = None) -> tuple[str, int]:
    """Generate a short-lived HMAC-SHA256 signature and expiration timestamp."""
    ttl = ttl_seconds or settings.SIGNED_URL_TTL_SECONDS
    exp = int(datetime.now(timezone.utc).timestamp()) + ttl
    msg = f"{resource_key}:{exp}".encode("utf-8")
    sig = hmac.new(
        settings.SIGNED_URL_SECRET.encode("utf-8"), msg, hashlib.sha256
    ).hexdigest()
    return sig, exp


def verify_signed_token(resource_key: str, sig: str, exp: int) -> bool:
    """Verify an HMAC-SHA256 signed download token and expiration."""
    now = int(datetime.now(timezone.utc).timestamp())
    if now > exp:
        return False
    msg = f"{resource_key}:{exp}".encode("utf-8")
    expected = hmac.new(
        settings.SIGNED_URL_SECRET.encode("utf-8"), msg, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def _get_fernet() -> Fernet:
    """Derive a valid Fernet key from configured ENCRYPTION_KEY or SECRET_KEY."""
    raw = settings.ENCRYPTION_KEY or settings.SECRET_KEY
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_sensitive_value(plaintext: str) -> str:
    """Encrypt sensitive field values at rest."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_sensitive_value(ciphertext: str) -> str:
    """Decrypt sensitive field values encrypted at rest."""
    return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


_PASSPORT_RE = re.compile(r"\b([A-Z]{1,2}\d{6,8})\b")
_IBAN_ACCT_RE = re.compile(r"\b(\d{8,16})\b")


def sanitize_log_metadata(data: Any) -> Any:
    """Strip or mask sensitive document details (passport/bank numbers) before logging or auditing."""
    if isinstance(data, dict):
        sanitized = {}
        sensitive_keys = {
            "passport_number",
            "account_number",
            "password",
            "hashed_password",
            "token",
            "access_token",
            "refresh_token",
            "api_key",
            "smtp_password",
            "resend_api_key",
        }
        for k, v in data.items():
            if k.lower() in sensitive_keys:
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = sanitize_log_metadata(v)
        return sanitized
    if isinstance(data, list):
        return [sanitize_log_metadata(item) for item in data]
    if isinstance(data, str):
        masked = _PASSPORT_RE.sub("***PASSPORT***", data)
        masked = _IBAN_ACCT_RE.sub("***NUMBER***", masked)
        return masked
    return data
