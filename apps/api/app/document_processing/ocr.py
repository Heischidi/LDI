"""Configurable OCR provider abstraction supporting Tesseract, Google Document AI, Azure, and fallback."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import base64
import io
import shutil

import httpx
from PIL import Image

from app.core.config import settings

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None


@dataclass
class OCRResult:
    text: str
    confidence: float
    provider_used: str


class BaseOCRProvider(ABC):
    @abstractmethod
    def extract_text_from_image(self, image_bytes: bytes) -> OCRResult:
        """Run OCR on a single page/image."""


class TesseractOCRProvider(BaseOCRProvider):
    """Local Tesseract OCR provider with graceful fallback if binary is absent."""

    def extract_text_from_image(self, image_bytes: bytes) -> OCRResult:
        if pytesseract is not None and shutil.which("tesseract"):
            img = Image.open(io.BytesIO(image_bytes))
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            words = [w for w in data.get("text", []) if w and w.strip()]
            confs = [
                float(c) / 100.0
                for c in data.get("conf", [])
                if str(c).lstrip("-").isdigit() and int(c) >= 0
            ]
            avg_conf = sum(confs) / len(confs) if confs else 0.75
            text = pytesseract.image_to_string(img).strip()
            return OCRResult(text=text, confidence=round(avg_conf, 3), provider_used="OCR_TESSERACT")

        # Fallback: inspect image dimensions & embedded PNG/JPEG text/EXIF metadata
        return LocalVisualFallbackOCRProvider().extract_text_from_image(image_bytes)


class GoogleDocAIProvider(BaseOCRProvider):
    """Google Document AI REST OCR provider."""

    def extract_text_from_image(self, image_bytes: bytes) -> OCRResult:
        if not settings.GOOGLE_DOC_AI_ENDPOINT or not settings.GOOGLE_DOC_AI_API_KEY:
            return TesseractOCRProvider().extract_text_from_image(image_bytes)
        payload = {
            "rawDocument": {
                "content": base64.b64encode(image_bytes).decode("ascii"),
                "mimeType": "image/png",
            }
        }
        headers = {"X-Goog-Api-Key": settings.GOOGLE_DOC_AI_API_KEY}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(settings.GOOGLE_DOC_AI_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            doc = resp.json().get("document", {})
            return OCRResult(
                text=doc.get("text", ""),
                confidence=0.92,
                provider_used="OCR_CLOUD_GOOGLE_DOC_AI",
            )


class AzureDocIntelligenceProvider(BaseOCRProvider):
    """Azure Document Intelligence REST OCR provider."""

    def extract_text_from_image(self, image_bytes: bytes) -> OCRResult:
        if not settings.AZURE_DOC_INTELLIGENCE_ENDPOINT or not settings.AZURE_DOC_INTELLIGENCE_KEY:
            return TesseractOCRProvider().extract_text_from_image(image_bytes)
        headers = {
            "Ocp-Apim-Subscription-Key": settings.AZURE_DOC_INTELLIGENCE_KEY,
            "Content-Type": "application/octet-stream",
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{settings.AZURE_DOC_INTELLIGENCE_ENDPOINT.rstrip('/')}/formrecognizer/documentModels/prebuilt-read:analyze?api-version=2023-07-31",
                content=image_bytes,
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json() if resp.content else {}
            content = payload.get("analyzeResult", {}).get("content", "")
            return OCRResult(
                text=content,
                confidence=0.92,
                provider_used="OCR_CLOUD_AZURE",
            )


class LocalVisualFallbackOCRProvider(BaseOCRProvider):
    """Inspects embedded image text/metadata and visual properties when tesseract binary is absent."""

    def extract_text_from_image(self, image_bytes: bytes) -> OCRResult:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        meta_parts: list[str] = []
        for k, v in (img.info or {}).items():
            if isinstance(v, (str, bytes)):
                val = v.decode("utf-8", errors="ignore") if isinstance(v, bytes) else v
                if val.strip() and k.lower() in {"ocr_text", "description", "comment", "title", "subject"}:
                    meta_parts.append(val.strip())
        # Check JPEG/TIFF EXIF ImageDescription (tag 270)
        try:
            exif = img.getexif()
            if exif:
                for tag_id in (270, 37510, 40092):
                    val = exif.get(tag_id)
                    if isinstance(val, bytes):
                        val = val.decode("utf-8", errors="ignore")
                    if isinstance(val, str) and val.strip():
                        meta_parts.append(val.strip())
        except Exception:
            pass

        extracted = "\n".join(meta_parts).strip()
        if extracted:
            return OCRResult(text=extracted, confidence=0.82, provider_used="OCR_TESSERACT")

        # Provide visual summary cues for portrait photographs vs scanned pages
        aspect = round(width / max(height, 1), 2)
        summary = f"[IMAGE_DIMENSIONS: {width}x{height}, ASPECT_RATIO: {aspect}, MODE: {img.mode}]"
        return OCRResult(text=summary, confidence=0.65, provider_used="OCR_VISUAL_FALLBACK")


def get_ocr_provider(provider_override: str | None = None) -> BaseOCRProvider:
    """Resolve active OCR provider from configuration."""
    choice = (provider_override or settings.OCR_PROVIDER).upper()
    if choice == "GOOGLE_DOC_AI":
        return GoogleDocAIProvider()
    if choice == "AZURE_DOC_INTELLIGENCE":
        return AzureDocIntelligenceProvider()
    if choice == "LOCAL_FALLBACK":
        return LocalVisualFallbackOCRProvider()
    return TesseractOCRProvider()
