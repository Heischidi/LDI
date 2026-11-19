"""Generate 17 realistic unnamed files + ZIP bundle for testing Canada Study Visa content-based organization."""

import io
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
API_DIR = ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from tests.conftest import make_docx_bytes, make_scanned_image_png, make_searchable_pdf  # noqa: E402


def build_unnamed_canada_documents(applicant_name: str = "Chidi Nwosu") -> list[tuple[str, bytes, str, str]]:
    """Return list of (unnamed_filename, raw_bytes, mime_type, expected_doc_type_code)."""
    surname, given = applicant_name.upper().split(" ", 1)
    return [
        (
            "IMG_0001.pdf",
            make_searchable_pdf(
                [
                    "INTERNATIONAL PASSPORT",
                    f"Surname: {surname}",
                    f"Given Names: {given}",
                    "Nationality: NIGERIAN",
                    "Passport No: A77889900",
                    "Issue Date: 2023-08-01",
                    "Expiry Date: 2028-07-31",
                    f"P<NGA{surname}<<{given}<<<<<<<<<<<<<<<<<<<<<<",
                ]
            ),
            "application/pdf",
            "INTERNATIONAL_PASSPORT",
        ),
        (
            "scan_0002.pdf",
            make_searchable_pdf(
                [
                    "University of Toronto - Office of Admissions",
                    "LETTER OF ACCEPTANCE (LOA)",
                    f"Applicant Name: {applicant_name}",
                    "Designated Learning Institution (DLI Number): O19332746152",
                    "Program: Master of Science in Computer Science",
                    "Issue Date: 2026-06-15",
                ]
            ),
            "application/pdf",
            "ADMISSION_LETTER",
        ),
        (
            "WhatsApp_Doc_3.pdf",
            make_searchable_pdf(
                [
                    "National Population Commission",
                    "CERTIFICATE OF BIRTH",
                    f"Full Name: {applicant_name}",
                    "Date of Birth: 2000-05-14",
                    "Place of Birth: Lagos, Nigeria",
                    "Registrar of Births · Issue Date: 2000-06-01",
                ]
            ),
            "application/pdf",
            "BIRTH_CERTIFICATE",
        ),
        (
            "untitled_04.pdf",
            make_searchable_pdf(
                [
                    "CURRICULUM VITAE",
                    f"Full Name: {applicant_name}",
                    "EDUCATION BACKGROUND: B.Sc. Computer Science (First Class Honours)",
                    "WORK EXPERIENCE: Software Engineer (2023 - 2026)",
                    "SKILLS: Python, Distributed Systems, Cloud Computing | REFEREES: Available on request",
                ]
            ),
            "application/pdf",
            "CURRICULUM_VITAE",
        ),
        (
            "file_05.pdf",
            make_searchable_pdf(
                [
                    "University of Nigeria Senate",
                    "DEGREE CERTIFICATE",
                    f"This is to certify that {applicant_name} has been conferred upon Bachelor of Science with Honours.",
                    "Issue Date: 2023-11-18",
                ]
            ),
            "application/pdf",
            "ACADEMIC_CERTIFICATES",
        ),
        (
            "doc_06.pdf",
            make_searchable_pdf(
                [
                    "University of Nigeria - Office of the Registrar",
                    "OFFICIAL DEGREE ACADEMIC TRANSCRIPT",
                    f"Student Name: {applicant_name}",
                    "Course Code CSC401 | Credits Earned: 150 | CGPA: 4.78",
                    "Issue Date: 2026-04-02",
                ]
            ),
            "application/pdf",
            "ACADEMIC_TRANSCRIPT",
        ),
        (
            "scan_07.pdf",
            make_searchable_pdf(
                [
                    "West African Examinations Council (WAEC)",
                    "WEST AFRICAN SENIOR SCHOOL CERTIFICATE (WASSCE)",
                    f"Candidate Name: {applicant_name}",
                    "Examination Number: 4250101999 | English: A1, Mathematics: A1, Physics: B2",
                    "Issue Date: 2018-08-20",
                ]
            ),
            "application/pdf",
            "WAEC_NECO_CERTIFICATE",
        ),
        (
            "card_08.pdf",
            make_searchable_pdf(
                [
                    "WAEC RESULT CHECKER SCRATCH CARD",
                    "Result Checker e-PIN: 882910334412",
                    "Serial Number: WR2026004491",
                    "Use this scratch card PIN to verify candidate WAEC examination results online.",
                ]
            ),
            "application/pdf",
            "WAEC_NECO_SCRATCH_CARD",
        ),
        (
            "letter_09.pdf",
            make_searchable_pdf(
                [
                    "ACADEMIC REFERENCE LETTER",
                    "Department of Computer Science · Letter of Recommendation",
                    f"Student Name: {applicant_name}",
                    "From: Professor A. Okonkwo, Head of Department",
                    "I strongly recommend this candidate based on outstanding academic performance and research.",
                    "Issue Date: 2026-06-10",
                ]
            ),
            "application/pdf",
            "ACADEMIC_REFERENCE_LETTER",
        ),
        (
            "photo_10.png",
            make_scanned_image_png("", portrait=True),
            "image/png",
            "PASSPORT_PHOTOGRAPH",
        ),
        (
            "slip_11.pdf",
            make_searchable_pdf(
                [
                    "National Identity Management Commission (NIMC)",
                    "NATIONAL IDENTIFICATION NUMBER (NIN SLIP)",
                    f"Full Name: {applicant_name}",
                    "Tracking ID: NIMC-TRK-99102 | Federal Republic of Nigeria",
                    "Issue Date: 2021-02-11",
                ]
            ),
            "application/pdf",
            "NIN_SLIP",
        ),
        (
            "clearance_12.pdf",
            make_searchable_pdf(
                [
                    "Nigeria Police Force - Central Criminal Registry",
                    "POLICE CLEARANCE CHARACTER CERTIFICATE",
                    f"Applicant Name: {applicant_name}",
                    "Fingerprints verified: No criminal convictions recorded.",
                    "Issue Date: 2026-09-12",
                ]
            ),
            "application/pdf",
            "POLICE_CLEARANCE",
        ),
        (
            "draft_13.docx",
            make_docx_bytes(
                [
                    "STATEMENT OF PURPOSE (SOP)",
                    f"Applicant Name: {applicant_name}",
                    "Dear Admissions and Visa Officer, my academic background and career goals inspired my application to Canada.",
                    "Reason for choosing the University of Toronto MSc program and future aspirations.",
                ]
            ),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "STATEMENT_OF_PURPOSE",
        ),
        (
            "work_14.pdf",
            make_searchable_pdf(
                [
                    "Zenith Tech Systems Ltd · Human Resources",
                    "LETTER OF EMPLOYMENT VERIFICATION",
                    f"Applicant Name: {applicant_name}",
                    "Job Title: Senior Software Engineer | Annual Salary: NGN 18,000,000 | Date of Hire: 2023-12-01",
                    "Issue Date: 2026-08-18",
                ]
            ),
            "application/pdf",
            "EMPLOYMENT_LETTER",
        ),
        (
            "acct_15.pdf",
            make_searchable_pdf(
                [
                    "Guaranty Trust Bank (GTBank)",
                    "BANK STATEMENT - SIX MONTHS STATEMENT OF ACCOUNT & BANK REFERENCE CERTIFICATE",
                    f"Account Holder: {applicant_name}",
                    "Account Number: 0123456789 | Currency: NGN",
                    "Opening Balance: NGN 42,000,000 | Closing Balance: NGN 58,500,000",
                    "Statement Date: 2026-10-25",
                ]
            ),
            "application/pdf",
            "BANK_STATEMENT",
        ),
        (
            "asset_16.pdf",
            make_searchable_pdf(
                [
                    "Ministry of Lands and Urban Development",
                    "CERTIFICATE OF OCCUPANCY (C OF O)",
                    f"Applicant Name: {applicant_name}",
                    "Statutory Right of Occupancy granted under Land Use Act for Plot 44 Lekki Phase 1.",
                    "Issue Date: 2022-04-05",
                ]
            ),
            "application/pdf",
            "CERTIFICATE_OF_OCCUPANCY",
        ),
        (
            "fee_17.pdf",
            make_searchable_pdf(
                [
                    "Chambers of A. Bello & Co · Notary Public & Solicitors",
                    "OFFICIAL PAYMENT RECEIPT - LAWYER'S NOTARY FEE",
                    f"Full Name: {applicant_name}",
                    "Amount Paid: NGN 100,000 (Legal Notarization Fee) | Notary Seal Affixed",
                    "Issue Date: 2026-10-10",
                ]
            ),
            "application/pdf",
            "NOTARY_FEE_RECEIPT",
        ),
    ]


def write_test_bundle(output_dir: Path | None = None) -> tuple[Path, Path]:
    """Write individual unnamed files + single ZIP archive to disk for manual UI upload testing."""
    out_dir = output_dir or (ROOT / "sample_unnamed_canada_files")
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = ROOT / "sample_unnamed_canada_bundle.zip"

    docs = build_unnamed_canada_documents()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, raw_bytes, _mime, _code in docs:
            (out_dir / fname).write_bytes(raw_bytes)
            zf.writestr(fname, raw_bytes)

    return out_dir, zip_path


if __name__ == "__main__":
    folder, bundle_zip = write_test_bundle()
    print(f"Generated {len(list(folder.iterdir()))} unnamed test files in {folder}")
    print(f"Generated ready-to-upload ZIP bundle at {bundle_zip}")
