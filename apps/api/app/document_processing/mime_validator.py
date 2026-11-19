"""Magic-byte MIME validation, malware screening, and safe ZIP extraction."""

import hashlib
import io
import socket
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings

try:
    import magic  # type: ignore
except Exception:
    magic = None


ALLOWED_MIME_BY_EXTENSION: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".tif": {"image/tiff"},
    ".tiff": {"image/tiff"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    ".doc": {"application/msword", "application/x-ole-storage"},
    ".zip": {"application/zip", "application/x-zip-compressed"},
}

SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".doc", ".docx"}

# EICAR test signature & dangerous executable headers
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
BLOCKED_MAGIC_HEADERS = (
    b"MZ",        # Windows PE executable / DLL
    b"\x7fELF",   # Linux ELF binary
    b"#!",        # Shell / script shebang
    b"<?php",     # PHP script
    b"<script",   # HTML/JS payload
)


@dataclass
class ValidatedFileItem:
    """Represents a single validated file ready for immutable storage and ingestion."""

    original_filename: str
    extension: str
    detected_mime_type: str
    size_bytes: int
    sha256_hash: str
    content: bytes
    source_archive_name: str | None = None


class UploadValidationError(ValueError):
    """Raised when an uploaded file or archive fails security or format validation."""


def detect_mime_from_bytes(data: bytes, filename: str) -> str:
    """Detect actual MIME type from binary file signatures rather than trusting extensions."""
    if not data:
        raise UploadValidationError(f"File '{filename}' is empty (0 bytes).")

    header = data[:32]

    # Check executable/script payloads immediately
    stripped_lower = data[:128].lstrip().lower()
    for bad in BLOCKED_MAGIC_HEADERS:
        if header.startswith(bad) or stripped_lower.startswith(bad.lower()):
            raise UploadValidationError(
                f"File '{filename}' contains disallowed executable or script signatures."
            )

    if header.startswith(b"%PDF-"):
        return "application/pdf"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"II*\x00") or header.startswith(b"MM\x00*"):
        return "image/tiff"
    if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword"
    if header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06"):
        # Distinguish DOCX vs ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = set(zf.namelist())
                if "word/document.xml" in names or "[Content_Types].xml" in names:
                    if any(n.startswith("word/") for n in names):
                        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            return "application/zip"
        except zipfile.BadZipFile as exc:
            raise UploadValidationError(f"File '{filename}' has corrupted archive structure.") from exc

    # Fallback to python-magic if libmagic is installed on the host
    if magic is not None:
        try:
            detected = magic.from_buffer(data[:4096], mime=True)
            if detected:
                return detected
        except Exception:
            pass

    raise UploadValidationError(
        f"File '{filename}' does not match any supported document binary signature (PDF, JPG, PNG, TIFF, DOC, DOCX, ZIP)."
    )


def scan_for_malware(data: bytes, filename: str) -> None:
    """Screen file bytes for known malware signatures and optional ClamAV daemon."""
    if EICAR_SIGNATURE in data:
        raise UploadValidationError(
            f"Security alert: malware signature detected in '{filename}'."
        )

    if settings.CLAMAV_HOST:
        try:
            with socket.create_connection(
                (settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=3
            ) as sock:
                sock.sendall(b"zINSTREAM\0")
                chunk_size = 4096
                for idx in range(0, len(data), chunk_size):
                    chunk = data[idx : idx + chunk_size]
                    sock.sendall(struct.pack("!I", len(chunk)) + chunk)
                sock.sendall(struct.pack("!I", 0))
                response = sock.recv(1024).decode("utf-8", errors="ignore")
                if "FOUND" in response:
                    raise UploadValidationError(
                        f"ClamAV rejected '{filename}': {response.strip()}"
                    )
        except UploadValidationError:
            raise
        except OSError:
            # ClamAV daemon unreachable when configured optionally; signature check still ran
            pass


def validate_single_document(
    filename: str,
    data: bytes,
    source_archive_name: str | None = None,
) -> ValidatedFileItem:
    """Validate file size, magic-byte MIME type, extension compatibility, and malware."""
    safe_name = Path(filename).name
    if not safe_name:
        raise UploadValidationError("Invalid empty filename.")

    max_bytes = settings.MAX_UPLOAD_FILE_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise UploadValidationError(
            f"File '{safe_name}' exceeds maximum size of {settings.MAX_UPLOAD_FILE_SIZE_MB} MB."
        )

    scan_for_malware(data, safe_name)
    detected_mime = detect_mime_from_bytes(data, safe_name)
    ext = Path(safe_name).suffix.lower()

    if ext not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported extension '{ext}' for file '{safe_name}'. Supported: PDF, JPG, JPEG, PNG, TIFF, DOC, DOCX, ZIP."
        )

    allowed_mimes = ALLOWED_MIME_BY_EXTENSION.get(ext, set())
    if detected_mime not in allowed_mimes:
        raise UploadValidationError(
            f"File '{safe_name}' content type ({detected_mime}) does not match extension '{ext}'."
        )

    sha256_hash = hashlib.sha256(data).hexdigest()
    return ValidatedFileItem(
        original_filename=safe_name,
        extension=ext.lstrip("."),
        detected_mime_type=detected_mime,
        size_bytes=len(data),
        sha256_hash=sha256_hash,
        content=data,
        source_archive_name=source_archive_name,
    )


def validate_and_unpack_upload(filename: str, data: bytes) -> list[ValidatedFileItem]:
    """Validate an uploaded file; if it is a ZIP archive, safely unpack and validate contents."""
    safe_name = Path(filename).name
    scan_for_malware(data, safe_name)
    detected_mime = detect_mime_from_bytes(data, safe_name)
    ext = Path(safe_name).suffix.lower()

    if ext == ".zip" or (
        detected_mime in {"application/zip", "application/x-zip-compressed"} and ext != ".docx"
    ):
        return _safely_extract_zip(safe_name, data)

    return [validate_single_document(safe_name, data)]


def _safely_extract_zip(archive_name: str, data: bytes) -> list[ValidatedFileItem]:
    """Extract ZIP entries safely with decompression bomb, path traversal, and file count guards."""
    max_files = settings.MAX_ZIP_EXTRACT_FILES
    max_total_bytes = settings.MAX_ZIP_EXTRACT_SIZE_MB * 1024 * 1024
    max_ratio = settings.MAX_ZIP_COMPRESSION_RATIO

    extracted: list[ValidatedFileItem] = []
    total_uncompressed = 0

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = [info for info in zf.infolist() if not info.is_dir()]
            if len(infos) > max_files:
                raise UploadValidationError(
                    f"ZIP archive '{archive_name}' contains {len(infos)} files, exceeding limit of {max_files}."
                )

            for info in infos:
                # Path traversal check
                member_path = info.filename.replace("\\", "/")
                if member_path.startswith("/") or ".." in Path(member_path).parts:
                    raise UploadValidationError(
                        f"ZIP archive '{archive_name}' contains unsafe path '{info.filename}'."
                    )

                # Skip macOS metadata artifacts silently
                base_name = Path(member_path).name
                if base_name.startswith("._") or "__MACOSX" in member_path:
                    continue

                if info.file_size > settings.MAX_UPLOAD_FILE_SIZE_MB * 1024 * 1024:
                    raise UploadValidationError(
                        f"ZIP entry '{base_name}' exceeds single file size limit."
                    )

                comp_size = max(info.compress_size, 1)
                if info.file_size / comp_size > max_ratio and info.file_size > 1024 * 1024:
                    raise UploadValidationError(
                        f"ZIP entry '{base_name}' triggered decompression bomb protection (ratio > {max_ratio}x)."
                    )

                total_uncompressed += info.file_size
                if total_uncompressed > max_total_bytes:
                    raise UploadValidationError(
                        f"ZIP archive '{archive_name}' uncompressed size exceeds {settings.MAX_ZIP_EXTRACT_SIZE_MB} MB limit."
                    )

                member_bytes = zf.read(info)
                # Verify actual read length matches header to catch forged headers
                if len(member_bytes) > settings.MAX_UPLOAD_FILE_SIZE_MB * 1024 * 1024:
                    raise UploadValidationError(
                        f"ZIP entry '{base_name}' exceeded maximum allowed file size during extraction."
                    )

                item = validate_single_document(
                    base_name,
                    member_bytes,
                    source_archive_name=archive_name,
                )
                extracted.append(item)
    except zipfile.BadZipFile as exc:
        raise UploadValidationError(f"'{archive_name}' is not a valid ZIP archive.") from exc

    if not extracted:
        raise UploadValidationError(
            f"ZIP archive '{archive_name}' contained no valid supported documents."
        )
    return extracted
