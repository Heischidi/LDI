# Leaders Document Intelligence (LDI)

Internal document intelligence, AI classification, compliance checking, and automated folder organisation platform built for **Leaders Edu Tour Ltd**.

> **Administrative Notice:** Leaders Document Intelligence is an administrative document management and organisation tool. Identification, classification confidence, and checklist checks do not certify authenticity or replace official immigration assessments.

---

## Architecture Overview

- **Frontend (`apps/web`)**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, Lucide Icons, React Hook Form, Zod, TanStack Query.
- **Backend (`apps/api`)**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic migrations, ReportLab PDF reporting.
- **Database**: PostgreSQL 16 (with seamless SQLite fallback for standalone local execution).
- **Async Background Jobs**: Celery + Redis (with automatic background thread-pool fallback when Redis is not running locally).
- **Document & AI Processing**: PyMuPDF, pdfplumber, Pillow, python-docx, Tesseract / Google Document AI / Azure Document Intelligence OCR abstraction, and interchangeable AI classifiers (Google Gemini API, OpenAI API, or Privacy-First Local Deterministic Content Analyzer).
- **Storage**: S3-compatible object storage (AWS S3, Cloudflare R2, MinIO) or private out-of-tree Local Vault with short-lived HMAC-signed URLs.

---

## Project Structure

```text
leaders-document-intelligence/
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── ai/                  # Gemini, OpenAI & Local Deterministic Classifiers + PII Redaction
│   │   │   ├── api/routes/          # REST API endpoints (auth, applicants, requirements, documents, processing, exports, dashboard, reports, users, audit, settings)
│   │   │   ├── core/                # Config, SQLAlchemy engine, JWT/bcrypt/Fernet security, RBAC deps
│   │   │   ├── document_processing/ # Magic-byte MIME validator, safe ZIP extractor, PyMuPDF/pdfplumber/DOCX/OCR extractor
│   │   │   ├── models/              # Normalized 23-table SQLAlchemy 2.0 schema
│   │   │   ├── schemas/             # Pydantic request/response & AI JSON validation schemas
│   │   │   ├── services/            # Requirements engine, naming engine, checklist reconciliation, intelligence pipeline, PDF/ZIP exporter, audit logger, seeder
│   │   │   ├── storage/             # S3 / R2 / MinIO and Local Vault private storage
│   │   │   └── workers/             # Celery tasks & async dispatcher
│   │   ├── migrations/              # Alembic migrations
│   │   └── tests/                   # Pytest unit & full E2E integration suite
│   └── web/                         # Next.js 14+ App Router frontend
├── infrastructure/
│   ├── docker/                      # Dockerfiles for API & Web
│   └── scripts/                     # End-to-end verification script
├── docs/                            # Architecture & Security/Compliance docs
├── docker-compose.yml
└── .env.example
```

---

## Quick Start (Docker Compose — Full Stack with PostgreSQL, Redis, MinIO)

```bash
cp .env.example .env
docker compose up --build
```

- **Frontend**: `http://localhost:3000`
- **Backend API & Swagger Docs**: `http://localhost:8000/docs`
- **MinIO Console**: `http://localhost:9001`

---

## Standalone Local Development (Without Docker)

### 1. Backend API
```bash
cd apps/api
.venv\Scripts\activate
alembic upgrade head
python -m app.services.seed_cli
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Web App
```bash
cd apps/web
npm install
npm run dev
```

### 3. Seeded Staff Accounts
| Role | Email | Password |
| :--- | :--- | :--- |
| Super Administrator | `superadmin@leaders.edu` | `LeadersAdmin!2026` |
| Administrator | `admin@leaders.edu` | `LeadersAdmin!2026` |
| Document Processing Officer | `officer@leaders.edu` | `LeadersOfficer!2026` |
| Viewer / Supervisor | `viewer@leaders.edu` | `LeadersViewer!2026` |

---

## Automated Verification

```bash
# Backend unit & full E2E 15-file pipeline tests
cd apps/api
.venv\Scripts\pytest.exe -v

# Standalone Section 24 Definition of Done script
python infrastructure/scripts/verify_e2e_john_doe.py

# Frontend tests & production build
cd apps/web
npm test
npm run build
```
