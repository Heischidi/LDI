"""Google Gemini, OpenAI, and privacy-first Deterministic Content AI classification providers."""

import json
import re
from datetime import datetime
from typing import Any

import httpx

from app.ai.base import BaseAIClassifier, redact_sensitive_pii
from app.core.config import settings
from app.schemas.ai import AIClassificationResult


def _build_classification_prompt(
    extracted_text: str,
    page_count: int,
    ingestion_type: str,
    available_doc_types: list[dict[str, str]],
) -> str:
    type_list = "\n".join(
        f"- {d['code']}: {d['name']} ({d.get('description') or ''})" for d in available_doc_types
    )
    return f"""You are a document intelligence classifier for Leaders Edu Tour Ltd.
Classify the document strictly based on its extracted content, layout labels, and metadata (NEVER rely on filenames).

Allowed document_type codes:
{type_list}
- UNKNOWN (if unreadable or cannot be identified)
- ADDITIONAL_DOCUMENT (if valid supporting document not in primary list)

Return ONLY a valid JSON object matching this exact schema:
{{
  "document_type": "<CODE>",
  "confidence": 0.95,
  "applicant_name": "Full Name or null",
  "document_number": "Reference/ID number or null",
  "issuing_organisation": "Authority/Institution/Bank or null",
  "issue_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "document_date": "YYYY-MM-DD or null",
  "page_count": {page_count},
  "is_readable": true,
  "is_incomplete": false,
  "possible_issues": [],
  "classification_reason": "Clear explanation referencing content cues"
}}

Ingestion type: {ingestion_type}
Extracted text (truncated to 8000 chars):
\"\"\"
{extracted_text[:8000]}
\"\"\"
"""


class GeminiAIClassifier(BaseAIClassifier):
    """Google Gemini API structured document classifier."""

    provider_name = "GEMINI"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model or settings.GEMINI_MODEL

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
        if not self.api_key:
            raise RuntimeError(
                "Gemini API key is not configured. Set GEMINI_API_KEY or switch AI_PROVIDER to LOCAL_DETERMINISTIC."
            )
        text_for_ai = (
            redact_sensitive_pii(extracted_text)
            if settings.REDACT_PII_BEFORE_EXTERNAL_AI
            else extracted_text
        )
        prompt = _build_classification_prompt(
            text_for_ai, page_count, ingestion_type, available_doc_types
        )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        raw_text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "{}")
        )
        parsed = json.loads(raw_text)
        return AIClassificationResult.model_validate(parsed)


class OpenAIAIClassifier(BaseAIClassifier):
    """OpenAI Chat Completions structured document classifier."""

    provider_name = "OPENAI"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model or settings.OPENAI_MODEL

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
        if not self.api_key:
            raise RuntimeError(
                "OpenAI API key is not configured. Set OPENAI_API_KEY or switch AI_PROVIDER to LOCAL_DETERMINISTIC."
            )
        text_for_ai = (
            redact_sensitive_pii(extracted_text)
            if settings.REDACT_PII_BEFORE_EXTERNAL_AI
            else extracted_text
        )
        prompt = _build_classification_prompt(
            text_for_ai, page_count, ingestion_type, available_doc_types
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You return only valid JSON matching the document classification schema.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw_text)
        return AIClassificationResult.model_validate(parsed)


class DeterministicContentClassifier(BaseAIClassifier):
    """Privacy-preserving local content/layout analyzer for offline operation & automated testing.

    Classifies strictly from extracted text, OCR output, structural markers, and image geometry —
    never from filenames.
    """

    provider_name = "LOCAL_DETERMINISTIC"
    model_name = "ldi-content-analyzer-v1"

    _DOC_RULES: list[tuple[str, list[tuple[str, float]], str]] = [
        (
            "INTERNATIONAL_PASSPORT",
            [
                (r"\bpassport\b", 0.35),
                (r"\bp<[a-z]{3}", 0.45),
                (r"\b(nationality|place of birth|date of expiry|passport no)\b", 0.30),
                (r"\bsurname\b.*\bgiven names?\b", 0.25),
            ],
            "Matched passport biodata fields, MRZ pattern, and travel document labels.",
        ),
        (
            "ADMISSION_LETTER",
            [
                (r"\b(unconditional offer|conditional offer|letter of admission|offer of admission|confirmation of acceptance for studies|\bcas\b)\b", 0.45),
                (r"\b(university|college|admissions office|tuition fee|academic program|enrolled)\b", 0.30),
                (r"\b(pleased to offer|admitted to|start date|course title)\b", 0.28),
            ],
            "Matched university/college admission offer terminology and enrollment details.",
        ),
        (
            "ACADEMIC_TRANSCRIPT",
            [
                (r"\b(official academic transcript|academic transcript|transcript of records)\b", 0.50),
                (r"\b(cgpa|gpa|credit hours|grade point|semester|course code)\b", 0.35),
                (r"\b(registrar|grade|credits earned)\b", 0.25),
            ],
            "Matched academic transcript structure with course grades, credits, and GPA/CGPA.",
        ),
        (
            "ACADEMIC_CERTIFICATES",
            [
                (r"\b(degree certificate|bachelor of|master of|hereby certifies|conferred upon)\b", 0.45),
                (r"\b(diploma|honours|graduation|senate|vice[- ]chancellor|waec|neco)\b", 0.32),
                (r"\b(certificate of completion|academic qualification)\b", 0.35),
            ],
            "Matched academic degree/diploma conferral and qualification wording.",
        ),
        (
            "BANK_STATEMENT",
            [
                (r"\b(bank statement|statement of account|account summary)\b", 0.45),
                (r"\b(opening balance|closing balance|available balance|transaction history|credit|debit)\b", 0.35),
                (r"\b(account number|iban|sort code|swift|currency)\b", 0.28),
            ],
            "Matched banking transaction ledger, balances, and account holder labels.",
        ),
        (
            "BIRTH_CERTIFICATE",
            [
                (r"\b(birth certificate|certificate of birth|national population commission)\b", 0.55),
                (r"\b(date of birth|place of birth|name of father|name of mother|registrar of births)\b", 0.35),
            ],
            "Matched vital statistics birth registration authority and parentage fields.",
        ),
        (
            "STATEMENT_OF_PURPOSE",
            [
                (r"\b(statement of purpose|personal statement|letter of motivation|study plan)\b", 0.50),
                (r"\b(career goals|academic background|reason for choosing|future aspirations|dear admissions)\b", 0.35),
            ],
            "Matched personal motivation essay structure and study/career objective statements.",
        ),
        (
            "ENGLISH_PROFICIENCY",
            [
                (r"\b(ielts|toefl|pte academic|duolingo english test|test report form)\b", 0.55),
                (r"\b(listening|reading|writing|speaking|overall band score|cefr level)\b", 0.35),
            ],
            "Matched standardized English proficiency test scores and sub-band breakdown.",
        ),
        (
            "PASSPORT_PHOTOGRAPH",
            [
                (r"\b(biometric passport photo|passport photograph|studio photo)\b", 0.55),
            ],
            "Matched biometric portrait dimensions and photographic attributes.",
        ),
        (
            "SPONSORSHIP_LETTER",
            [
                (r"\b(letter of sponsorship|financial sponsor|affidavit of support|undertake to sponsor)\b", 0.50),
                (r"\b(tuition and living expenses|relationship to applicant|sponsor)\b", 0.30),
            ],
            "Matched financial sponsorship commitment and relationship declaration.",
        ),
        (
            "MEDICAL_CERTIFICATE",
            [
                (r"\b(tuberculosis|tb clearance|medical certificate|iom clinic|chest x-ray|medical fitness)\b", 0.55),
                (r"\b(physician|examined|no active pulmonary)\b", 0.30),
            ],
            "Matched medical screening / TB clearance clinical wording.",
        ),
        (
            "EMPLOYMENT_LETTER",
            [
                (r"\b(employment verification|letter of employment|to whom it may concern.*employed)\b", 0.45),
                (r"\b(job title|annual salary|human resources|date of hire)\b", 0.35),
            ],
            "Matched employer verification and compensation details.",
        ),
        (
            "POLICE_CLEARANCE",
            [
                (r"\b(police clearance|criminal record check|character certificate|interpol)\b", 0.55),
                (r"\b(no criminal convictions|fingerprints)\b", 0.35),
            ],
            "Matched police character / criminal background clearance indicators.",
        ),
        (
            "TRAVEL_ITINERARY",
            [
                (r"\b(flight itinerary|booking reference|pnr|departure|arrival|airline)\b", 0.50),
            ],
            "Matched flight booking reservation details.",
        ),
        (
            "HOTEL_BOOKING",
            [
                (r"\b(hotel reservation|check-in|check-out|accommodation confirmation)\b", 0.50),
            ],
            "Matched accommodation booking confirmation details.",
        ),
    ]

    _NAME_PATTERNS = [
        re.compile(
            r"(?:applicant\s*name|full\s*name|student\s*name|account\s*holder|name\s*of\s*child|candidate\s*name|dear|issued\s*to)\s*[:\-]\s*([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,3})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:surname|last\s*name)\s*[:\-]\s*([A-Z][a-zA-Z'\-]+).*?(?:given\s*names?|first\s*name)\s*[:\-]\s*([A-Z][a-zA-Z'\-]+)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"(?:pleased to offer|hereby certifies that|confirm that|this is to certify that)\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,2})",
            re.IGNORECASE,
        ),
    ]
    _DOC_NO_RE = re.compile(
        r"(?:passport\s*no\.?|document\s*no\.?|reference\s*no\.?|certificate\s*no\.?|cas\s*number|account\s*no\.?|trf\s*number|student\s*id)\s*[:\-#]?\s*([A-Z0-9\-/]{5,24})",
        re.IGNORECASE,
    )
    _ISSUER_RE = re.compile(
        r"(?:issuing\s*(?:authority|organisation|organization|institution)|university|bank|ministry|commission|board)\s*[:\-]\s*([^\n]{3,80})",
        re.IGNORECASE,
    )
    _ISSUE_DATE_RE = re.compile(
        r"(?:issue\s*date|date\s*of\s*issue|statement\s*date|dated|test\s*date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}[/\-]\d{2}[/\-]\d{4})",
        re.IGNORECASE,
    )
    _EXPIRY_DATE_RE = re.compile(
        r"(?:expiry\s*date|date\s*of\s*expiry|valid\s*until|expires\s*on)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}[/\-]\d{2}[/\-]\d{4})",
        re.IGNORECASE,
    )
    _ANY_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

    def _normalize_date(self, val: str | None) -> str | None:
        if not val:
            return None
        val = val.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
            return val
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _extract_name(self, text: str) -> str | None:
        for pat in self._NAME_PATTERNS:
            m = pat.search(text)
            if m:
                if len(m.groups()) == 2:
                    return f"{m.group(2).strip()} {m.group(1).strip()}".title()
                candidate = " ".join(m.group(1).strip().split())
                # Strip trailing common stop words
                candidate = re.split(r"\b(has|was|is|born|on|for|at|from)\b", candidate, flags=re.I)[0].strip()
                if len(candidate.split()) >= 2:
                    return candidate.title()
        return None

    def _extract_issuer(self, text: str, doc_type: str) -> str | None:
        m = self._ISSUER_RE.search(text)
        if m:
            return m.group(1).strip().rstrip(".,;")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("---")]
        if lines and len(lines[0]) <= 80:
            if doc_type in {"BANK_STATEMENT", "ADMISSION_LETTER", "ACADEMIC_TRANSCRIPT", "ACADEMIC_CERTIFICATES"}:
                return lines[0]
        return None

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
        lower = extracted_text.lower()
        issues: list[str] = []

        if is_blurry:
            issues.append("Blurry or low-resolution scan detected; manual inspection recommended.")
        if not is_readable:
            issues.append("Document text readability is very low or empty.")

        # Portrait image detection without needing text
        if ingestion_type == "IMAGE" and detected_metadata.get("is_portrait_like"):
            return AIClassificationResult(
                document_type="PASSPORT_PHOTOGRAPH",
                confidence=0.93,
                applicant_name=None,
                document_number=None,
                issuing_organisation=None,
                issue_date=None,
                expiry_date=None,
                document_date=None,
                page_count=page_count,
                is_readable=is_readable,
                is_incomplete=False,
                possible_issues=issues,
                classification_reason="Image matches biometric passport photograph aspect ratio and clarity.",
            )

        best_type = "UNKNOWN"
        best_score = 0.0
        best_reason = "Insufficient content signals to classify reliably."

        for doc_code, patterns, reason in self._DOC_RULES:
            score = 0.0
            hits = 0
            for pat, weight in patterns:
                if re.search(pat, lower, re.DOTALL):
                    score += weight
                    hits += 1
            if hits >= 2:
                score = min(0.98, score + 0.12)
            elif hits == 1:
                score = min(0.79, score + 0.10)
            if score > best_score:
                best_score = score
                best_type = doc_code
                best_reason = reason

        # Check for ambiguous/weak or irrelevant documents
        if best_score < 0.35:
            # Check if document has substantial coherent text (could be additional or unknown)
            if "utility bill" in lower or "electricity" in lower or "receipt" in lower or "menu" in lower:
                best_type = "ADDITIONAL_DOCUMENT"
                best_score = 0.58
                best_reason = "Document appears to be a miscellaneous/additional receipt or utility notice."
                issues.append("Document does not match standard required visa checklist categories.")
            else:
                best_type = "UNKNOWN"
                best_score = max(0.25, round(best_score, 2))
                issues.append("Low confidence classification; manual review required.")

        if is_blurry:
            best_score = min(best_score, 0.68)
        if not is_readable and best_type != "PASSPORT_PHOTOGRAPH":
            best_score = min(best_score, 0.45)

        extracted_name = self._extract_name(extracted_text)
        doc_no_match = self._DOC_NO_RE.search(extracted_text)
        doc_no = doc_no_match.group(1).strip() if doc_no_match else None
        issue_dt = self._normalize_date(
            self._ISSUE_DATE_RE.search(extracted_text).group(1)
            if self._ISSUE_DATE_RE.search(extracted_text)
            else None
        )
        expiry_dt = self._normalize_date(
            self._EXPIRY_DATE_RE.search(extracted_text).group(1)
            if self._EXPIRY_DATE_RE.search(extracted_text)
            else None
        )
        any_dt_match = self._ANY_DATE_RE.search(extracted_text)
        doc_dt = issue_dt or (any_dt_match.group(1) if any_dt_match else None)
        issuer = self._extract_issuer(extracted_text, best_type)

        # Check completeness hints
        is_incomplete = "page 1 of 2" in lower and page_count == 1
        if is_incomplete:
            issues.append("Document indicates multi-page sequence (e.g. Page 1 of 2) but only 1 page was found.")

        return AIClassificationResult(
            document_type=best_type,
            confidence=round(min(0.99, max(0.05, best_score)), 3),
            applicant_name=extracted_name,
            document_number=doc_no,
            issuing_organisation=issuer,
            issue_date=issue_dt,
            expiry_date=expiry_dt,
            document_date=doc_dt,
            page_count=page_count,
            is_readable=is_readable,
            is_incomplete=is_incomplete,
            possible_issues=issues,
            classification_reason=best_reason,
        )


def get_ai_classifier(
    provider_override: str | None = None,
    allow_external: bool | None = None,
) -> BaseAIClassifier:
    """Resolve configured AI provider while enforcing privacy policy (ALLOW_EXTERNAL_AI)."""
    provider = (provider_override or settings.AI_PROVIDER).upper()
    external_allowed = settings.ALLOW_EXTERNAL_AI if allow_external is None else allow_external

    if not external_allowed or provider == "LOCAL_DETERMINISTIC":
        return DeterministicContentClassifier()
    if provider == "GEMINI":
        return GeminiAIClassifier()
    if provider == "OPENAI":
        return OpenAIAIClassifier()
    return DeterministicContentClassifier()
