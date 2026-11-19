"""Pytest fixtures and realistic synthetic document generators (PDF, scanned image, DOCX, ZIP)."""

import io
import os
from pathlib import Path
import tempfile
import zipfile

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None  # type: ignore

from docx import Document as DocxDocument
from PIL import Image, ImageDraw, PngImagePlugin
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas


def make_searchable_pdf(lines: list[str]) -> bytes:
    """Create a real searchable multi-line PDF document via PyMuPDF or ReportLab."""
    if fitz is not None:
        doc = fitz.open()
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((60, y), line, fontsize=12)
            y += 20
        return doc.tobytes()

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.showPage()
    c.save()
    return buf.getvalue()


def make_scanned_image_png(ocr_text: str, *, blurry: bool = False, portrait: bool = False) -> bytes:
    """Create a real PNG image (either scanned document with embedded OCR cue or portrait photo)."""
    width, height = (400, 500) if portrait else (800, 1000)
    img = Image.new("RGB", (width, height), color=(248, 250, 252))
    draw = ImageDraw.Draw(img)
    if portrait:
        # Draw high-contrast portrait silhouette so edge sharpness passes biometric clarity
        draw.rectangle([40, 40, 360, 460], outline=(11, 31, 58), width=4)
        draw.ellipse([130, 110, 270, 260], fill=(180, 140, 120), outline=(40, 40, 40), width=3)
        draw.rectangle([100, 275, 300, 430], fill=(15, 81, 50), outline=(20, 20, 20), width=2)
    elif not blurry:
        draw.rectangle([50, 50, 750, 950], outline=(30, 41, 59), width=3)
        for idx, line in enumerate(ocr_text.splitlines()[:12]):
            draw.text((80, 90 + idx * 30), line, fill=(15, 23, 42))

    meta = PngImagePlugin.PngInfo()
    if ocr_text:
        meta.add_text("ocr_text", ocr_text)
    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


def make_docx_bytes(paragraphs: list[str]) -> bytes:
    """Create a real Word .docx document in memory."""
    doc = DocxDocument()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_zip_bytes(entries: dict[str, bytes]) -> bytes:
    """Create a ZIP archive in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.fixture(scope="session")
def test_env_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="function")
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide an isolated TestClient with fresh DB and private storage vault per test."""
    db_path = tmp_path / "test_ldi.db"
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("LOCAL_VAULT_PATH", vault_path.as_posix())
    monkeypatch.setenv("CELERY_ALWAYS_EAGER", "true")
    monkeypatch.setenv("AI_PROVIDER", "LOCAL_DETERMINISTIC")
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "false")

    # Reset cached settings and rebind database engine for test isolation
    from app.core import config, database

    config.get_settings.cache_clear()
    new_settings = config.get_settings()
    config.settings = new_settings
    database.settings = new_settings
    database.engine.dispose()
    database.engine = database._build_engine()
    database.SessionLocal.configure(bind=database.engine)

    # Refresh module-level references that imported `settings` or `engine`
    from app import main as app_main
    from app.core import security
    from app.storage import service as storage_service

    app_main.settings = new_settings
    app_main.engine = database.engine
    security.settings = new_settings
    storage_service.settings = new_settings

    with TestClient(app_main.app) as c:
        yield c


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
