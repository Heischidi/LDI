"""Document text, page, and visual quality extraction using PyMuPDF, pdfplumber, Pillow, python-docx."""

import hashlib
import io
import re
from dataclasses import dataclass, field
from typing import Any

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None  # type: ignore

import pdfplumber
from docx import Document as DocxDocument
from PIL import Image, ImageFilter, ImageStat

from app.document_processing.ocr import get_ocr_provider


@dataclass
class ExtractionOutput:
    ingestion_type: str  # SEARCHABLE_PDF | SCANNED_PDF | IMAGE | WORD_DOC
    extraction_method: str
    raw_text: str
    normalized_text_hash: str
    page_count: int
    page_texts: list[dict[str, Any]] = field(default_factory=list)
    page_images_b64: list[str] = field(default_factory=list)
    ocr_confidence: float | None = None
    is_readable: bool = True
    is_blurry: bool = False
    is_incomplete: bool = False
    detected_metadata: dict[str, Any] = field(default_factory=dict)


def _normalize_text_for_hash(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def _estimate_image_sharpness(image: Image.Image) -> float:
    """Measure edge variance using Pillow FIND_EDGES filter (excluding border artifact) to flag blurry scans."""
    gray = image.convert("L")
    # Downscale very large scans for fast consistent metric
    gray.thumbnail((1200, 1200))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    w, h = edges.size
    if w > 12 and h > 12:
        edges = edges.crop((4, 4, w - 4, h - 4))
    stat = ImageStat.Stat(edges)
    return float(stat.var[0])


def _is_portrait_like(width: int, height: int, sharpness: float, text_len: int) -> bool:
    """Detect whether an image resembles a passport/ID photograph rather than a scanned document page."""
    if text_len > 5:
        return False
    ratio = width / max(height, 1)
    return 0.65 <= ratio <= 1.15 and width >= 150 and height >= 150 and sharpness > 12.0


def extract_document_content(
    data: bytes,
    detected_mime_type: str,
    extension: str,
    ocr_provider_name: str | None = None,
) -> ExtractionOutput:
    """Inspect binary document, determine ingestion type, extract text/OCR, and check readability."""
    if detected_mime_type == "application/pdf":
        return _extract_pdf(data, ocr_provider_name=ocr_provider_name)
    if detected_mime_type.startswith("image/"):
        return _extract_image(data, ocr_provider_name=ocr_provider_name)
    if (
        detected_mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or extension.lower() == "docx"
    ):
        return _extract_docx(data)
    if detected_mime_type == "application/msword" or extension.lower() == "doc":
        return _extract_legacy_doc(data)

    raise ValueError(f"Unsupported MIME type for extraction: {detected_mime_type}")


def _extract_pdf(data: bytes, ocr_provider_name: str | None = None) -> ExtractionOutput:
    """Extract embedded text from PDF pages via PyMuPDF + pdfplumber, falling back to OCR for scanned pages."""
    ocr_provider = get_ocr_provider(ocr_provider_name)
    plumber_texts: list[str] = []
    pdf_meta: dict[str, Any] = {}
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pdf_meta = {k: str(v) for k, v in (pdf.metadata or {}).items() if v}
            for p in pdf.pages:
                plumber_texts.append((p.extract_text() or "").strip())
    except Exception:
        plumber_texts = []

    if fitz is None:
        page_count = len(plumber_texts)
        page_texts = [
            {
                "page_number": idx + 1,
                "text": txt,
                "char_count": len(txt),
                "method": "PDFPLUMBER",
            }
            for idx, txt in enumerate(plumber_texts)
        ]
        full_text = "\n\n".join(
            f"--- PAGE {p['page_number']} ---\n{p['text']}" for p in page_texts if p["text"]
        ).strip()
        return ExtractionOutput(
            ingestion_type="SEARCHABLE_PDF" if full_text else "SCANNED_PDF",
            extraction_method="PDFPLUMBER",
            raw_text=full_text,
            normalized_text_hash=_normalize_text_for_hash(full_text),
            page_count=page_count,
            page_texts=page_texts,
            ocr_confidence=None,
            is_readable=len(full_text) >= 15,
            is_blurry=False,
            is_incomplete="page 1 of 2" in full_text.lower() and page_count == 1,
            detected_metadata={"pdf_metadata": pdf_meta},
        )

    doc = fitz.open(stream=data, filetype="pdf")
    page_count = len(doc)
    if page_count == 0:
        return ExtractionOutput(
            ingestion_type="SEARCHABLE_PDF",
            extraction_method="PYMUPDF",
            raw_text="",
            normalized_text_hash=_normalize_text_for_hash(""),
            page_count=0,
            is_readable=False,
            is_incomplete=True,
            detected_metadata={"warning": "PDF has zero pages"},
        )

    page_texts: list[dict[str, Any]] = []
    ocr_confidences: list[float] = []
    blurry_pages = 0
    scanned_pages = 0
    if not plumber_texts:
        plumber_texts = [""] * page_count

    for idx in range(page_count):
        page = doc[idx]
        fitz_text = (page.get_text("text") or "").strip()
        plum_text = plumber_texts[idx] if idx < len(plumber_texts) else ""
        embedded_text = fitz_text if len(fitz_text) >= len(plum_text) else plum_text

        method = "PYMUPDF" if fitz_text >= plum_text else "PDFPLUMBER"
        if len(embedded_text) < 25:
            # Scanned PDF page -> render bitmap and run OCR + sharpness check
            scanned_pages += 1
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            pil_img = Image.open(io.BytesIO(img_bytes))
            sharpness = _estimate_image_sharpness(pil_img)
            if sharpness < 18.0:
                blurry_pages += 1
            ocr_res = ocr_provider.extract_text_from_image(img_bytes)
            page_text = ocr_res.text
            method = ocr_res.provider_used
            ocr_confidences.append(ocr_res.confidence)
        else:
            page_text = embedded_text

        page_texts.append(
            {
                "page_number": idx + 1,
                "text": page_text,
                "char_count": len(page_text),
                "method": method,
            }
        )

    full_text = "\n\n".join(
        f"--- PAGE {p['page_number']} ---\n{p['text']}" for p in page_texts if p["text"]
    ).strip()

    ingestion_type = "SCANNED_PDF" if scanned_pages == page_count else "SEARCHABLE_PDF"
    extraction_method = (
        "OCR_TESSERACT"
        if scanned_pages == page_count
        else ("PYMUPDF" if any(p["method"] == "PYMUPDF" for p in page_texts) else "PDFPLUMBER")
    )
    avg_ocr_conf = (
        round(sum(ocr_confidences) / len(ocr_confidences), 3) if ocr_confidences else None
    )

    # Flag readability issues
    is_blurry = blurry_pages > 0 and blurry_pages >= (page_count / 2)
    is_readable = len(full_text) >= 15 and not is_blurry
    is_incomplete = "page 1 of 2" in full_text.lower() and page_count == 1

    return ExtractionOutput(
        ingestion_type=ingestion_type,
        extraction_method=extraction_method,
        raw_text=full_text,
        normalized_text_hash=_normalize_text_for_hash(full_text),
        page_count=page_count,
        page_texts=page_texts,
        ocr_confidence=avg_ocr_conf,
        is_readable=is_readable,
        is_blurry=is_blurry,
        is_incomplete=is_incomplete,
        detected_metadata={
            "pdf_metadata": {k: str(v) for k, v in (doc.metadata or {}).items() if v},
            "scanned_pages": scanned_pages,
            "blurry_pages": blurry_pages,
        },
    )


def _extract_image(data: bytes, ocr_provider_name: str | None = None) -> ExtractionOutput:
    """Run sharpness assessment and OCR on image files (JPG, PNG, TIFF)."""
    img = Image.open(io.BytesIO(data))
    width, height = img.size
    sharpness = _estimate_image_sharpness(img)

    # Convert to PNG bytes for uniform OCR handling
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    png_bytes = buf.getvalue()

    ocr_provider = get_ocr_provider(ocr_provider_name)
    ocr_res = ocr_provider.extract_text_from_image(data if img.format == "PNG" else png_bytes)

    # Check if image is an actual portrait photo vs blurry scan
    raw_text = ocr_res.text.strip()
    is_portrait = _is_portrait_like(width, height, sharpness, len(re.sub(r"\[IMAGE_DIMENSIONS:.*?\]", "", raw_text)))
    is_blurry = sharpness < 15.0 and not is_portrait
    is_readable = not is_blurry and (len(raw_text) >= 10 or is_portrait)

    return ExtractionOutput(
        ingestion_type="IMAGE",
        extraction_method=ocr_res.provider_used,
        raw_text=raw_text,
        normalized_text_hash=_normalize_text_for_hash(raw_text),
        page_count=getattr(img, "n_frames", 1),
        page_texts=[
            {
                "page_number": 1,
                "text": raw_text,
                "char_count": len(raw_text),
                "method": ocr_res.provider_used,
            }
        ],
        ocr_confidence=ocr_res.confidence,
        is_readable=is_readable,
        is_blurry=is_blurry,
        is_incomplete=False,
        detected_metadata={
            "width": width,
            "height": height,
            "sharpness": round(sharpness, 2),
            "is_portrait_like": is_portrait,
            "format": img.format,
        },
    )


def _extract_docx(data: bytes) -> ExtractionOutput:
    """Extract paragraphs and tables from Word .docx files."""
    doc = DocxDocument(io.BytesIO(data))
    chunks: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            chunks.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_vals = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_vals:
                chunks.append(" | ".join(row_vals))

    full_text = "\n".join(chunks).strip()
    approx_pages = max(1, len(full_text) // 2500 + 1) if full_text else 1

    return ExtractionOutput(
        ingestion_type="WORD_DOC",
        extraction_method="PYTHON_DOCX",
        raw_text=full_text,
        normalized_text_hash=_normalize_text_for_hash(full_text),
        page_count=approx_pages,
        page_texts=[
            {
                "page_number": 1,
                "text": full_text,
                "char_count": len(full_text),
                "method": "PYTHON_DOCX",
            }
        ],
        ocr_confidence=1.0,
        is_readable=len(full_text) >= 15,
        is_blurry=False,
        is_incomplete=False,
        detected_metadata={"paragraph_count": len(doc.paragraphs), "table_count": len(doc.tables)},
    )


def _extract_legacy_doc(data: bytes) -> ExtractionOutput:
    """Best-effort ASCII/UTF-16 string extraction from legacy .doc OLE binary streams."""
    ascii_runs = re.findall(rb"[\x20-\x7e]{6,}", data)
    text = "\n".join(run.decode("ascii", errors="ignore") for run in ascii_runs[:400]).strip()
    return ExtractionOutput(
        ingestion_type="WORD_DOC",
        extraction_method="LEGACY_DOC_EXTRACTOR",
        raw_text=text,
        normalized_text_hash=_normalize_text_for_hash(text),
        page_count=1,
        page_texts=[{"page_number": 1, "text": text, "char_count": len(text), "method": "LEGACY_DOC"}],
        ocr_confidence=0.75,
        is_readable=len(text) >= 20,
        is_blurry=False,
        is_incomplete=False,
        detected_metadata={"legacy_doc": True},
    )
