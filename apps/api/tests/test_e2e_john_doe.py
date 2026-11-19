"""End-to-end Definition of Done test (Section 24): John Doe 15-file workflow."""

import io
import zipfile

from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    make_docx_bytes,
    make_scanned_image_png,
    make_searchable_pdf,
)


def test_section_24_definition_of_done_john_doe_15_files(client: TestClient):
    """Verify full Section 24 scenario end-to-end with 15 randomly named files."""
    officer_hdrs = auth_headers(client, "officer@leaders.edu", "LeadersOfficer!2026")

    # 1. Select UK + Study + Student Visa
    dests = {d["code"]: d for d in client.get("/api/reference/destinations", headers=officer_hdrs).json()}
    purps = {p["code"]: p for p in client.get("/api/reference/purposes", headers=officer_hdrs).json()}
    cats = {c["code"]: c for c in client.get("/api/reference/categories", headers=officer_hdrs).json()}

    # 2. Create John Doe
    create_resp = client.post(
        "/api/applicants",
        json={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone_number": "+2348011223344",
            "nationality": "Nigerian",
            "passport_number": "A55443322",
            "destination_id": dests["GB"]["id"],
            "purpose_id": purps["STUDY"]["id"],
            "category_id": cats["STUDENT_VISA"]["id"],
        },
        headers=officer_hdrs,
    )
    assert create_resp.status_code == 201
    applicant = create_resp.json()
    applicant_id = applicant["id"]
    assert len(applicant["checklist"]) >= 9

    # 3. Prepare 15 randomly-named documents covering PDFs, scanned PNGs, DOCX, duplicate, mismatch, uncertain & irrelevant
    passport_pdf = make_searchable_pdf(
        [
            "INTERNATIONAL PASSPORT",
            "Surname: DOE",
            "Given Names: JOHN",
            "Passport No: A55443322",
            "Nationality: NIGERIAN",
            "Issue Date: 2023-05-01",
            "Expiry Date: 2028-04-30",
            "P<NGADOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<",
        ]
    )
    admission_pdf = make_searchable_pdf(
        [
            "University of Leeds - Admissions Office",
            "Unconditional Offer Letter of Admission",
            "Applicant Name: John Doe",
            "CAS Number: UKCAS-77219",
            "Issue Date: 2026-07-12",
        ]
    )
    transcript_pdf = make_searchable_pdf(
        [
            "University of Lagos - Registrar",
            "OFFICIAL ACADEMIC TRANSCRIPT",
            "Student Name: John Doe",
            "Course Code | Credits Earned | Grade Point | CGPA: 4.52",
            "Issue Date: 2026-03-10",
        ]
    )
    degree_pdf = make_searchable_pdf(
        [
            "University of Lagos Senate",
            "DEGREE CERTIFICATE",
            "This is to certify that John Doe has been conferred upon Bachelor of Science with Honours.",
            "Issue Date: 2025-11-20",
        ]
    )
    bank_stmt_1 = make_searchable_pdf(
        [
            "First Horizon Bank",
            "BANK STATEMENT - STATEMENT OF ACCOUNT",
            "Account Holder: John Doe",
            "Account Number: 0044556677",
            "Opening Balance: NGN 25,000,000",
            "Closing Balance: NGN 31,400,000",
            "Statement Date: 2026-10-20",
        ]
    )
    bank_stmt_2 = make_searchable_pdf(
        [
            "Zenith Savings Bank",
            "BANK STATEMENT - ACCOUNT SUMMARY",
            "Account Holder: John Doe",
            "Account Number: 0099887766",
            "Opening Balance: GBP 8,000",
            "Closing Balance: GBP 12,500",
            "Statement Date: 2026-10-25",
        ]
    )
    birth_cert_img = make_scanned_image_png(
        "National Population Commission\nCERTIFICATE OF BIRTH\nFull Name: John Doe\nDate of Birth: 2001-04-12\nPlace of Birth: Lagos\nRegistrar of Births"
    )
    sop_docx = make_docx_bytes(
        [
            "STATEMENT OF PURPOSE",
            "Applicant Name: John Doe",
            "Dear Admissions Committee, my academic background and career goals led me to pursue an MSc in the United Kingdom.",
            "Reason for choosing this program and future aspirations in data engineering.",
        ]
    )
    # Intentionally omit ENGLISH_PROFICIENCY so system detects it as MISSING!
    passport_photo = make_scanned_image_png("", portrait=True)
    # 10: Exact duplicate of bank_stmt_1 under different random name
    dup_bank = bank_stmt_1
    # 11: Name mismatch document
    mismatched_doc = make_searchable_pdf(
        [
            "IOM Medical Clinic",
            "MEDICAL CERTIFICATE - TB CLEARANCE",
            "Applicant Name: Michael Brown",
            "Examined for tuberculosis: No active pulmonary TB.",
            "Issue Date: 2026-09-01",
        ]
    )
    # 12: Uncertain / blurry scan requiring officer correction
    uncertain_doc = make_scanned_image_png("Unclear faded scan page", blurry=True)
    # 13: Irrelevant document (grocery receipt / utility) to exclude
    irrelevant_doc = make_searchable_pdf(
        [
            "City Superstore Receipt #4412",
            "Utility bill and electricity token receipt",
            "Total Paid: 45.00",
        ]
    )
    # 14 & 15: Two extra supporting documents (Sponsor letter & second transcript page)
    sponsor_pdf = make_searchable_pdf(
        [
            "LETTER OF SPONSORSHIP",
            "I undertake to sponsor John Doe for full tuition and living expenses.",
            "Relationship to applicant: Father",
            "Issue Date: 2026-10-05",
        ]
    )
    extra_transcript = make_searchable_pdf(
        [
            "OFFICIAL ACADEMIC TRANSCRIPT - SUPPLEMENTARY",
            "Student Name: John Doe",
            "Semester 8 Credit Hours and Final CGPA 4.52",
            "Issue Date: 2026-03-11",
        ]
    )

    files_15 = [
        ("IMG_0012.pdf", passport_pdf, "application/pdf"),
        ("WhatsApp_Image_2026.pdf", admission_pdf, "application/pdf"),
        ("document-final-2.pdf", transcript_pdf, "application/pdf"),
        ("file_12345.pdf", degree_pdf, "application/pdf"),
        ("doc_a_01.pdf", bank_stmt_1, "application/pdf"),
        ("doc_a_02.pdf", bank_stmt_2, "application/pdf"),
        ("scan0001.png", birth_cert_img, "image/png"),
        ("essay_draft_9.docx", sop_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("IMG_9981.png", passport_photo, "image/png"),
        ("passport-new.pdf", dup_bank, "application/pdf"),
        ("misc_scan_77.pdf", mismatched_doc, "application/pdf"),
        ("blurry_page_03.png", uncertain_doc, "image/png"),
        ("random_receipt_88.pdf", irrelevant_doc, "application/pdf"),
        ("letter_v3.pdf", sponsor_pdf, "application/pdf"),
        ("scan_extra_2.pdf", extra_transcript, "application/pdf"),
    ]
    assert len(files_15) == 15

    upload_resp = client.post(
        "/api/documents/upload",
        data={"applicant_id": applicant_id},
        files=[("files", f) for f in files_15],
        headers=officer_hdrs,
    )
    assert upload_resp.status_code == 201
    assert upload_resp.json()["total_accepted"] == 15
    batch_id = upload_resp.json()["batch_id"]

    # 4. Run AI Processing
    proc = client.post("/api/processing/batches?sync=true", json={"batch_id": batch_id}, headers=officer_hdrs)
    assert proc.status_code == 200

    # Check batch results
    batch_status = client.get(f"/api/processing/batches/{batch_id}/status", headers=officer_hdrs).json()
    docs = {d["original_filename"]: d for d in batch_status["documents"]}

    # Verify duplicate, mismatch, and uncertain detections
    assert docs["passport-new.pdf"]["is_duplicate"] is True
    assert docs["misc_scan_77.pdf"]["classification"]["has_name_mismatch"] is True
    assert docs["blurry_page_03.png"]["classification"]["confidence_tier"] == "LOW"

    # 5. Check missing requirement (ENGLISH_PROFICIENCY was omitted!)
    app_after = client.get(f"/api/applicants/{applicant_id}", headers=officer_hdrs).json()
    chk_by_code = {c["document_type_code"]: c for c in app_after["checklist"]}
    assert chk_by_code["ENGLISH_PROFICIENCY"]["status"] == "MISSING"

    # 6. Officer corrects uncertain doc (reclassifies to ENGLISH_PROFICIENCY) and excludes irrelevant doc
    uncertain_id = docs["blurry_page_03.png"]["id"]
    corr_resp = client.patch(
        f"/api/documents/{uncertain_id}/classification",
        json={
            "action": "CHANGE_TYPE",
            "document_type_code": "ENGLISH_PROFICIENCY",
            "notes": "Officer verified IELTS score sheet manually.",
        },
        headers=officer_hdrs,
    )
    assert corr_resp.status_code == 200
    client.post(f"/api/documents/{uncertain_id}/approve", headers=officer_hdrs)

    irrelevant_id = docs["random_receipt_88.pdf"]["id"]
    excl_resp = client.patch(
        f"/api/documents/{irrelevant_id}/classification",
        json={"action": "EXCLUDE", "notes": "Irrelevant store receipt."},
        headers=officer_hdrs,
    )
    assert excl_resp.status_code == 200
    assert excl_resp.json()["is_excluded"] is True

    # 7. Bulk approve remaining high-confidence valid documents, and explicitly approve sponsor/mismatched as needed
    client.post(
        "/api/documents/bulk-approve",
        json={"applicant_id": applicant_id, "min_confidence": 0.85},
        headers=officer_hdrs,
    )
    for fname in ["IMG_9981.png", "scan0001.png", "essay_draft_9.docx", "letter_v3.pdf", "scan_extra_2.pdf"]:
        doc_obj = docs[fname]
        client.post(f"/api/documents/{doc_obj['id']}/approve", headers=officer_hdrs)

    # 8. Generate organized export ZIP
    export_resp = client.post(f"/api/applicants/{applicant_id}/export", headers=officer_hdrs)
    assert export_resp.status_code == 200
    exp = export_resp.json()
    root = exp["folder_root"]
    assert "UNITED_KINGDOM/STUDY/JOHN_DOE_" in root

    # Download ZIP and verify exact compliance with Section 24
    zip_resp = client.get(exp["download_url"], headers=officer_hdrs)
    assert zip_resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
        names = zf.namelist()
        root_files = [
            n[len(root) + 1 :]
            for n in names
            if n.startswith(root + "/") and "ORIGINAL_DOCUMENTS/" not in n
        ]
        # Verify standardized ordered filenames exist
        assert "01_International_Passport.pdf" in root_files
        assert "02_Admission_Letter.pdf" in root_files
        assert "05_Bank_Statement_1.pdf" in root_files
        assert "05_Bank_Statement_2.pdf" in root_files
        assert "PROCESSING_REPORT.pdf" in root_files
        assert "processing_manifest.json" in root_files

        # Verify excluded irrelevant receipt & duplicate are NOT in approved root folder
        assert all("random_receipt" not in f for f in root_files)
        assert all("DUPLICATE" not in f for f in root_files)

        # Verify all 15 original files remain preserved inside ORIGINAL_DOCUMENTS/
        orig_files = [n for n in names if n.startswith(f"{root}/ORIGINAL_DOCUMENTS/")]
        assert len(orig_files) == 15

    # 9. Verify applicant record remains accessible with full history later
    final_app = client.get(f"/api/applicants/{applicant_id}", headers=officer_hdrs).json()
    assert len(final_app["exports"]) == 1
    assert len(final_app["batches"]) == 1
