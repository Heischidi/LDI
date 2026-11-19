# Security, Deployment & Compliance Guide

## 1. Authentication & Role-Based Access Control (RBAC)
- Passwords hashed with `bcrypt` (12 salt rounds).
- Short-lived JWT access tokens (30 min default) + refresh tokens (7 days) with revocation (`jti` tracking on logout/refresh).
- Brute-force login protection locks accounts temporarily after `MAX_LOGIN_ATTEMPTS` (default 5) failed logins.
- Server-side RBAC enforced on every endpoint via `require_roles` / `require_permission` dependencies (`SUPER_ADMIN`, `ADMIN`, `OFFICER`, `VIEWER`).

## 2. Document Storage & Private Access
- Uploaded source documents are stored immutably in private object storage (`originals/{APP_REF}/{BATCH_ID}/...`) and never placed inside the application source tree or public static folders.
- Supports AWS S3 (SSE-AES256), Cloudflare R2, MinIO, and an out-of-tree Local Vault.
- Downloads use authenticated API endpoints or short-lived HMAC-SHA256 signed URLs (`SIGNED_URL_TTL_SECONDS=300`).

## 3. Data Protection (NDPA & GDPR Alignment)
- Sensitive fields (`passport_number`) are encrypted at rest with Fernet (`AES-128-CBC` + `HMAC-SHA256`).
- Application logs and immutable `audit_logs` sanitize passport numbers, bank account numbers, passwords, and tokens (`sanitize_log_metadata`).
- External AI calls (`GEMINI` / `OPENAI`) can be disabled completely (`ALLOW_EXTERNAL_AI=false`) or stripped of PII (`REDACT_PII_BEFORE_EXTERNAL_AI=true`).

## 4. Production Deployment Checklist
- **Frontend (Vercel)**: Deploy `apps/web` with `NEXT_PUBLIC_API_URL=https://api.yourdomain.com`.
- **Backend & Celery Worker (Railway / Render / AWS)**: Deploy `infrastructure/docker/Dockerfile.api` for both the FastAPI web process and the Celery worker process (`celery -A app.workers.celery_app.celery_app worker --loglevel=info`).
- **Managed Infrastructure**: Configure managed PostgreSQL 16 (`DATABASE_URL`), managed Redis (`REDIS_URL` / `CELERY_BROKER_URL`), and private S3/R2 bucket (`STORAGE_BACKEND=s3` or `r2`).
- **Secrets**: Generate strong random 64-character values for `SECRET_KEY`, `SIGNED_URL_SECRET`, and `ENCRYPTION_KEY`.
