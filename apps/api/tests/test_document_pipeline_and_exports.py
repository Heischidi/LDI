"""Tests for upload validation, ZIP safety, OCR/text extraction, duplicate detection, naming, and exports."""

import zipfile
import io

from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    make_docx_bytes,
    make_scanned_image_png,
    make_searchable_pdf,
    make_zip_bytes,
)


def _create_uk_study_applicant(client: TestClient, hdrs: dict[str, str], first="John", last="Doe") -> dict:
    dests = {d["code"]: d for d in client.get("/api/reference/destinations", headers=hdrs).json()}
    purps = {p["code"]: p for p in client.get("/api/reference/purposes", headers=hdrs).json()}
    cats = {c["code"]: c for c in client.get("/api/reference/categories", headers=hdrs).json()}
    r = client.post(
        "/api/applicants",
        json={
            "first_name": first,
            "last_name": last,
            "email": f"{first.lower()}.{last.lower()}@example.com",
            "phone_number": "+2348000001111",
            "nationality": "Nigerian",
            "destination_id": dests["GB"]["id"],
            "purpose_id": purps["STUDY"]["id"],
            "category_id": cats["STUDENT_VISA"]["id"],
        },
        headers=hdrs,
    )
    assert r.status_code == 201
    return r.json()


def test_upload_validation_blocks_spoofed_and_malicious_files(client: TestClient):
    officer_hdrs = auth_headers(client, "officer@leaders.edu", "LeadersOfficer!2026")
    app_data = _create_uk_study_applicant(client, officer_hdrs)

    # Spoofed executable disguised as .pdf
    r_exe = client.post(
        "/api/documents/upload",
        data={"applicant_id": app_data["id"]},
        files=[("files", ("fake.pdf", b"MZ\x90\x00\x03\x00\x00\x00fake-executable", "application/pdf"))],
        headers=officer_hdrs,
    )
    assert r_exe.status_code == 400

    # EICAR test signature
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    r_eicar = client.post(
        "/api/documents/upload",
        data={"applicant_id": app_data["id"]},
        files=[("files", ("scan.pdf", eicar, "application/pdf"))],
        headers=officer_hdrs,
    )
    assert r_eicar.status_code == 400

    # ZIP path traversal attempt
    bad_zip = make_zip_bytes({"../../evil.pdf": make_searchable_pdf(["test"])})
    r_zip = client.post(
        "/api/documents/upload",
        data={"applicant_id": app_data["id"]},
        files=[("files", ("archive.zip", bad_zip, "application/zip"))],
        headers=officer_hdrs,
    )
    assert r_zip.status_code == 400


def test_zip_unpack_ocr_duplicate_naming_and_export(client: TestClient):
    officer_hdrs = auth_headers(client, "officer@leaders.edu", "LeadersOfficer!2026")
    app_data = _create_uk_study_applicant(client, officer_hdrs)

    passport_pdf = make_searchable_pdf(
        [
            "INTERNATIONAL PASSPORT - BIO DATA PAGE",
            "Surname: DOE",
            "Given Names: JOHN",
            "Nationality: NIGERIAN",
            "Passport No: A99887766",
            "Date of Issue: 2024-01-10",
            "Date of Expiry: 2029-01-09",
            "P<NGADOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<",
        ]
    )
    admission_docx = make_docx_bytes(
        [
            "University of Manchester - Admissions Office",
            "Unconditional Offer of Admission",
            "Student Name: John Doe",
            "CAS Number: E4G889911",
            "Course Title: MSc Computer Science",
            "Issue Date: 2026-06-15",
        ]
    )
    bank_img = make_scanned_image_png(
        "Example Bank\nBANK STATEMENT - STATEMENT OF ACCOUNT\nAccount Holder: John Doe\nAccount Number: 1029384756\nOpening Balance: GBP 15,000\nClosing Balance: GBP 24,500\nStatement Date: 2026-10-01"
    )
    # Exact duplicate of passport under a completely different random filename
    zip_bundle = make_zip_bytes(
        {
            "IMG_0012.pdf": passport_pdf,
            "WhatsApp_Doc_2026.docx": admission_docx,
            "scan0001.png": bank_img,
            "random_copy_file.pdf": passport_pdf,
        }
    )

    up_resp = client.post(
        "/api/documents/upload",
        data={"applicant_id": app_data["id"]},
        files=[("files", ("client_docs.zip", zip_bundle, "application/zip"))],
        headers=officer_hdrs,
    )
    assert up_resp.status_code == 201
    batch_id = up_resp.json()["batch_id"]
    assert up_resp.json()["total_accepted"] == 4

    # Run synchronous batch processing
    proc_resp = client.post(
        "/api/processing/batches?sync=true",
        json={"batch_id": batch_id},
        headers=officer_hdrs,
    )
    assert proc_resp.status_code == 200

    status_resp = client.get(f"/api/processing/batches/{batch_id}/status", headers=officer_hdrs)
    assert status_resp.status_code == 200
    docs = status_resp.json()["documents"]
    assert len(docs) == 4

    # Verify duplicate detection flagged the copy
    dups = [d for d in docs if d["is_duplicate"]]
    assert len(dups) == 1
    assert "SHA-256" in (dups[0]["duplicate_reason"] or "")

    # Verify filename-independent classification worked
    by_orig = {d["original_filename"]: d for d in docs}
    assert by_orig["IMG_0012.pdf"]["classification"]["predicted_type_code"] == "INTERNATIONAL_PASSPORT"
    assert by_orig["WhatsApp_Doc_2026.docx"]["classification"]["predicted_type_code"] == "ADMISSION_LETTER"
    assert by_orig["scan0001.png"]["classification"]["predicted_type_code"] == "BANK_STATEMENT"

    # Bulk approve high confidence non-duplicates
    bulk = client.post(
        "/api/documents/bulk-approve",
        json={"applicant_id": app_data["id"], "min_confidence": 0.85},
        headers=officer_hdrs,
    )
    assert bulk.status_code == 200
    assert bulk.json()["approved_count"] >= 2

    # Approve remaining non-duplicate docs explicitly
    for d in docs:
        if not d["is_duplicate"] and not d["is_approved_for_export"]:
            client.post(f"/api/documents/{d['id']}/approve", headers=officer_hdrs)

    # Generate ZIP export
    exp_resp = client.post(f"/api/applicants/{app_data['id']}/export", headers=officer_hdrs)
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()
    assert exp_data["approved_doc_count"] == 3

    # Download ZIP & inspect structure
    zip_dl = client.get(exp_data["download_url"], headers=officer_hdrs)
    assert zip_dl.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_dl.content)) as zf:
        names = zf.namelist()
        root = exp_data["folder_root"]
        assert f"{root}/01_International_Passport.pdf" in names
        assert f"{root}/02_Admission_Letter.docx" in names
        assert f"{root}/05_Bank_Statement.png" in names
        assert f"{root}/PROCESSING_REPORT.pdf" in names
        assert f"{root}/processing_manifest.json" in names
        # All 4 original files preserved inside ORIGINAL_DOCUMENTS
        orig_entries = [n for n in names if f"{root}/ORIGINAL_DOCUMENTS/" in n]
        assert len(orig_entries) == 4
        # Duplicate is NOT at export root
        assert not any("DUPLICATE" in n for n in names if "ORIGINAL_DOCUMENTS" not in n)

    # Signed URL download also works
    signed_dl = client.get(exp_data["signed_download_url"])
    assert signed_dl.status_code == 200

    # Verify audit trail captured events
    admin_hdrs = auth_headers(client, "admin@leaders.edu", "LeadersAdmin!2026")
    audits = client.get("/api/audit-logs", headers=admin_hdrs).json()["items"]
    actions = {a["action"] for a in audits}
    assert "FOLDER_EXPORTED" in actions
    assert "FOLDER_DOWNLOADED" in actions
