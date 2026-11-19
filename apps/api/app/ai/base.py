"""Abstract AI classifier contract and PII redaction helpers."""

from abc import ABC, abstractmethod
import re
from typing import Any

from app.schemas.ai import AIClassificationResult


_PASSPORT_NO_RE = re.compile(r"\b([A-Z]{1,2}\d{6,8})\b")
_LONG_DIGIT_RE = re.compile(r"\b(\d{9,18})\b")


def redact_sensitive_pii(text: str) -> str:
    """Minimize sensitive numbers (passport numbers, bank account numbers) sent to external AI providers."""
    redacted = _PASSPORT_NO_RE.sub(lambda m: f"{m.group(1)[:2]}******", text)
    redacted = _LONG_DIGIT_RE.sub(lambda m: f"****{m.group(1)[-4:]}", redacted)
    return redacted


class BaseAIClassifier(ABC):
    """Provider-independent document classification interface."""

    provider_name: str = "BASE"
    model_name: str = "unknown"

    @abstractmethod
    def classify(
        self,
        *,
        extracted_text: str,
        page_count: int,
        ingestion_type: str,
        is_readable: bool,
        is_blurry: bool,
        detected_metadata: dict[str, Any],
        available_doc_types: list[dict[str, str]],
        applicant_context: dict[str, Any],
    ) -> AIClassificationResult:
        """Classify a document purely from extracted content, layout cues, and visual metadata."""
