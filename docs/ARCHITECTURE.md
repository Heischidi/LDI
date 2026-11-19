# Architecture & Data Protection Guide

## 1. Document Intelligence Pipeline
1. **File Ingestion & Security Validation (`mime_validator.py`)**:
   - Inspects raw binary magic headers (`%PDF-`, JPEG, PNG, TIFF, OLE `.doc`, ZIP/DOCX) rather than trusting filenames or extensions.
   - Blocks executables (`MZ`, `ELF`, `#!`, `<script`, `<?php`), checks for EICAR/ClamAV malware signatures, and safely unpacks ZIP archives with path traversal checks, file count caps, uncompressed byte caps, and decompression-bomb ratio checks.
   - Stores original bytes immutably under `originals/{APP_REF}/{BATCH_ID}/...` in private storage (S3/R2/MinIO/Local Vault).
2. **Text & Image Extraction (`extractor.py`)**:
   - Extracts embedded text per page via `PyMuPDF` and `pdfplumber`.
   - Renders scanned PDF pages and images for sharpness assessment (blur detection) and OCR (`Tesseract`, `Google Document AI`, `Azure Document Intelligence`, or local fallback).
   - Extracts paragraphs and tables from `.docx` files via `python-docx`.
3. **Provider-Independent AI Classification (`ai/providers.py`)**:
   - Enforces structured JSON validated through Pydantic `AIClassificationResult`.
   - Supports Google Gemini, OpenAI, and privacy-preserving Local Deterministic Content Analysis.
   - Automatically strips/masks passport numbers and bank account numbers (`redact_sensitive_pii`) before sending content to external providers when `REDACT_PII_BEFORE_EXTERNAL_AI=true`, and allows disabling external AI altogether (`ALLOW_EXTERNAL_AI=false`).
4. **Confidence, Duplicate & Applicant Matching (`intelligence_pipeline.py`)**:
   - Confidence Tiers: `HIGH` (>=90%), `MEDIUM` (70–89%), `LOW` (<70%).
   - Exact duplicate detection via `SHA-256` hash + semantic duplicate detection via normalized text hash. Duplicates are flagged for review, never auto-deleted.
   - Compares extracted applicant names against the `Applicant` record and raises mismatch warnings.
5. **Configurable Requirements & Version Pinning (`requirements_engine.py`, `checklist_service.py`)**:
   - Requirements are defined in database tables (`requirement_sets`, `requirement_versions`, `document_requirements`) with logical conditions, aliases, alternative document types, and expiry checks.
   - Applicants are pinned to a `requirement_version_id` so subsequent checklist edits create new versions without silently altering existing applicant files.
6. **Automatic Naming & Folder Packaging (`naming_engine.py`, `export_service.py`)**:
   - Generates ordered standardized filenames (e.g. `01_International_Passport.pdf`, `05_Bank_Statement_1.pdf`, `05_Bank_Statement_2.pdf`).
   - Packages approved non-excluded documents alongside `ORIGINAL_DOCUMENTS/`, `PROCESSING_REPORT.pdf`, and `processing_manifest.json` into a downloadable ZIP served via authenticated endpoints or short-lived HMAC-signed URLs.

## 2. NDPA & GDPR Compliance Controls
- **Encryption at Rest**: Passport numbers encrypted via Fernet (`AES-128-CBC` + `HMAC-SHA256`), passwords hashed with `bcrypt`, S3 server-side encryption enabled.
- **PII-Sanitized Immutable Audit Logs**: Sensitive identifiers are masked (`***PASSPORT***`, `***NUMBER***`) before persisting to `audit_logs`.
- **RBAC Enforcement**: Enforced server-side on every FastAPI dependency (`require_roles` / `require_permission`), backed by account lockout and JWT token revocation.
