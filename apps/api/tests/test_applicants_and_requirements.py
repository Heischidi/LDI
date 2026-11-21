"""Tests for applicant CRUD, requirements matching, and checklist version preservation."""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_applicant_crud_and_search_filters(client: TestClient):
    officer_hdrs = auth_headers(client, "officer@leaders.edu", "LeadersOfficer!2026")
    admin_hdrs = auth_headers(client, "admin@leaders.edu", "LeadersAdmin!2026")

    dests = {d["code"]: d for d in client.get("/api/reference/destinations", headers=officer_hdrs).json()}
    purps = {p["code"]: p for p in client.get("/api/reference/purposes", headers=officer_hdrs).json()}
    cats = {c["code"]: c for c in client.get("/api/reference/categories", headers=officer_hdrs).json()}

    r = client.post(
        "/api/applicants",
        json={
            "first_name": "Chidi",
            "last_name": "Nwosu",
            "email": "chidi.nwosu@example.com",
            "phone_number": "+2348099998888",
            "nationality": "Nigerian",
            "passport_number": "A12345678",
            "destination_id": dests["GB"]["id"],
            "purpose_id": purps["STUDY"]["id"],
            "category_id": cats["STUDENT_VISA"]["id"],
        },
        headers=officer_hdrs,
    )
    assert r.status_code == 201
    app_data = r.json()
    assert app_data["application_reference"].startswith("LDI-")
    assert app_data["passport_number_masked"] == "A1*****78"
    assert len(app_data["checklist"]) >= 9

    # Search by reference and email
    search_resp = client.get(
        f"/api/applicants?search={app_data['application_reference']}",
        headers=officer_hdrs,
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] == 1

    # Soft archive
    del_resp = client.delete(f"/api/applicants/{app_data['id']}", headers=admin_hdrs)
    assert del_resp.status_code == 200
    active_list = client.get("/api/applicants", headers=officer_hdrs).json()
    assert active_list["total"] == 0


def test_requirements_matching_and_version_preservation(client: TestClient):
    admin_hdrs = auth_headers(client, "admin@leaders.edu", "LeadersAdmin!2026")
    officer_hdrs = auth_headers(client, "officer@leaders.edu", "LeadersOfficer!2026")

    dests = {d["code"]: d for d in client.get("/api/reference/destinations", headers=officer_hdrs).json()}
    purps = {p["code"]: p for p in client.get("/api/reference/purposes", headers=officer_hdrs).json()}
    cats = {c["code"]: c for c in client.get("/api/reference/categories", headers=officer_hdrs).json()}

    matched = client.get(
        "/api/requirements/match",
        params={
            "destination_id": dests["GB"]["id"],
            "purpose_id": purps["STUDY"]["id"],
            "category_id": cats["STUDENT_VISA"]["id"],
        },
        headers=officer_hdrs,
    )
    assert matched.status_code == 200
    req_set = matched.json()
    v1_id = req_set["active_version_id"]
    v1_count = len(req_set["active_version"]["items"])

    # Create applicant pinned to v1
    app_resp = client.post(
        "/api/applicants",
        json={
            "first_name": "Amaka",
            "last_name": "Obi",
            "email": "amaka@example.com",
            "phone_number": "+2348012345678",
            "nationality": "Nigerian",
            "destination_id": dests["GB"]["id"],
            "purpose_id": purps["STUDY"]["id"],
            "category_id": cats["STUDENT_VISA"]["id"],
        },
        headers=officer_hdrs,
    )
    applicant_id = app_resp.json()["id"]
    assert app_resp.json()["requirement_version_id"] == v1_id

    # Admin updates RequirementSet -> creates version 2
    first_item = req_set["active_version"]["items"][0]
    patch_resp = client.patch(
        f"/api/requirements/{req_set['id']}",
        json={
            "change_notes": "Trimmed to single item in v2 for testing",
            "items": [
                {
                    "document_type_id": first_item["document_type_id"],
                    "requirement_level": "REQUIRED",
                    "display_order": 1,
                }
            ],
        },
        headers=admin_hdrs,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["active_version"]["version_number"] == 2
    assert patch_resp.json()["active_version_id"] != v1_id

    # Verify existing applicant remains pinned to v1 with original item count
    reloaded = client.get(f"/api/applicants/{applicant_id}", headers=officer_hdrs).json()
    assert reloaded["requirement_version_id"] == v1_id
    assert len(reloaded["checklist"]) == v1_count


def test_client_stage_updates_and_email_reminders(client: TestClient):
    officer_hdrs = auth_headers(client, "officer@leaders.edu", "LeadersOfficer!2026")
    dests = {d["code"]: d for d in client.get("/api/reference/destinations", headers=officer_hdrs).json()}
    purps = {p["code"]: p for p in client.get("/api/reference/purposes", headers=officer_hdrs).json()}
    cats = {c["code"]: c for c in client.get("/api/reference/categories", headers=officer_hdrs).json()}

    catalog_resp = client.get("/api/applicants/stages/catalog", headers=officer_hdrs)
    assert catalog_resp.status_code == 200
    catalog = catalog_resp.json()
    assert "ADMISSION" in catalog and "VISA_PROCESSING" in catalog and "DOCUMENT_REMINDER" in catalog

    app_resp = client.post(
        "/api/applicants",
        json={
            "first_name": "Kelechi",
            "last_name": "Okoro",
            "email": "kelechi.okoro@example.com",
            "phone_number": "+2348055551111",
            "nationality": "Nigerian",
            "destination_id": dests["CA"]["id"],
            "purpose_id": purps["STUDY"]["id"],
            "category_id": cats["STUDY_PERMIT"]["id"],
        },
        headers=officer_hdrs,
    )
    assert app_resp.status_code == 201
    applicant_id = app_resp.json()["id"]

    # Send a Missing Documents Reminder (should include auto-detected missing items in body)
    rem_resp = client.post(
        f"/api/applicants/{applicant_id}/stage-updates",
        json={
            "track": "DOCUMENT_REMINDER",
            "stage_code": "MISSING_DOCUMENTS_REMINDER",
            "include_missing_checklist": True,
            "update_applicant_status": True,
        },
        headers=officer_hdrs,
    )
    assert rem_resp.status_code == 201, rem_resp.text
    rem = rem_resp.json()
    assert rem["recipient_email"] == "kelechi.okoro@example.com"
    assert rem["delivery_status"] == "LOGGED_READY"
    assert "Outstanding Required Documents" in rem["message_body"]
    assert "International Passport" in rem["message_body"]

    # Update milestone to Visa Approved
    visa_resp = client.post(
        f"/api/applicants/{applicant_id}/stage-updates",
        json={
            "track": "VISA_PROCESSING",
            "stage_code": "VISA_APPROVED",
            "include_missing_checklist": False,
            "update_applicant_status": True,
        },
        headers=officer_hdrs,
    )
    assert visa_resp.status_code == 201, visa_resp.text

    detail = client.get(f"/api/applicants/{applicant_id}", headers=officer_hdrs).json()
    assert detail["status"] == "VISA_APPROVED"
    assert detail["current_stage_code"] == "VISA_APPROVED"
    assert len(detail["stage_updates"]) == 2


def test_single_and_batch_delete_across_endpoints(client: TestClient):
    officer_hdrs = auth_headers(client, "officer@leaders.edu", "LeadersOfficer!2026")
    super_hdrs = auth_headers(client, "superadmin@leaders.edu", "LeadersAdmin!2026")

    dests = {d["code"]: d for d in client.get("/api/reference/destinations", headers=officer_hdrs).json()}
    purps = {p["code"]: p for p in client.get("/api/reference/purposes", headers=officer_hdrs).json()}
    cats = {c["code"]: c for c in client.get("/api/reference/categories", headers=officer_hdrs).json()}

    # 1. Create two applicants for officer and verify single + batch document/batch/applicant deletes
    created_apps = []
    for idx in range(2):
        r = client.post(
            "/api/applicants",
            json={
                "first_name": f"Delete{idx}",
                "last_name": "Tester",
                "email": f"delete.tester{idx}@example.com",
                "phone_number": "+2348012345678",
                "nationality": "Nigerian",
                "destination_id": dests["GB"]["id"],
                "purpose_id": purps["STUDY"]["id"],
                "category_id": cats["STUDENT_VISA"]["id"],
            },
            headers=officer_hdrs,
        )
        assert r.status_code == 201
        created_apps.append(r.json()["id"])

    # Upload 3 valid PDF files to applicant 0 so we have 1 batch & 3 docs
    from tests.conftest import make_searchable_pdf

    pdf1 = make_searchable_pdf(["Delete Tester Doc 1"])
    pdf2 = make_searchable_pdf(["Delete Tester Doc 2"])
    pdf3 = make_searchable_pdf(["Delete Tester Doc 3"])
    up_resp = client.post(
        "/api/documents/upload",
        data={"applicant_id": created_apps[0]},
        files=[
            ("files", ("doc_one.pdf", pdf1, "application/pdf")),
            ("files", ("doc_two.pdf", pdf2, "application/pdf")),
            ("files", ("doc_three.pdf", pdf3, "application/pdf")),
        ],
        headers=officer_hdrs,
    )
    assert up_resp.status_code == 201, up_resp.text
    batch_id = up_resp.json()["batch_id"]
    doc_ids = [d["id"] for d in up_resp.json()["documents"]]

    # Single delete document
    del_doc = client.delete(f"/api/documents/{doc_ids[0]}", headers=officer_hdrs)
    assert del_doc.status_code == 200
    assert client.get(f"/api/documents/{doc_ids[0]}", headers=officer_hdrs).status_code == 404

    # Batch delete remaining documents
    batch_del_docs = client.post(
        "/api/documents/batch-delete",
        json={"ids": doc_ids[1:]},
        headers=officer_hdrs,
    )
    assert batch_del_docs.status_code == 200
    assert batch_del_docs.json()["deleted_count"] == 2

    # Upload another batch then test batch delete processing batches + single batch delete
    up2 = client.post(
        "/api/documents/upload",
        data={"applicant_id": created_apps[0]},
        files=[("files", ("b2.pdf", make_searchable_pdf(["Batch Two Doc"]), "application/pdf"))],
        headers=officer_hdrs,
    )
    assert up2.status_code == 201
    batch2_id = up2.json()["batch_id"]
    assert client.delete(f"/api/processing/batches/{batch_id}", headers=officer_hdrs).status_code == 200
    bdel_batches = client.post(
        "/api/processing/batches/batch-delete",
        json={"ids": [batch2_id]},
        headers=officer_hdrs,
    )
    assert bdel_batches.status_code == 200
    assert bdel_batches.json()["deleted_count"] == 1

    # Approve and generate export, then delete export via batch-delete
    passport_pdf = make_searchable_pdf(
        [
            "INTERNATIONAL PASSPORT",
            "Surname: TESTER",
            "Given Names: DELETE1",
            "Passport No: A11223344",
        ]
    )
    up3 = client.post(
        "/api/documents/upload",
        data={"applicant_id": created_apps[1]},
        files=[("files", ("passport.pdf", passport_pdf, "application/pdf"))],
        headers=officer_hdrs,
    )
    assert up3.status_code == 201
    b3_id = up3.json()["batch_id"]
    proc3 = client.post("/api/processing/batches?sync=true", json={"batch_id": b3_id}, headers=officer_hdrs)
    assert proc3.status_code == 200
    doc3_id = up3.json()["documents"][0]["id"]
    app3_doc = client.post(f"/api/documents/{doc3_id}/approve", headers=officer_hdrs)
    assert app3_doc.status_code == 200
    exp1 = client.post(f"/api/applicants/{created_apps[1]}/export", headers=officer_hdrs)
    exp2 = client.post(f"/api/applicants/{created_apps[1]}/export", headers=officer_hdrs)
    assert exp1.status_code == 200 and exp2.status_code == 200
    assert client.delete(f"/api/exports/{exp1.json()['export_id']}", headers=officer_hdrs).status_code == 200
    bdel_exp = client.post(
        "/api/exports/batch-delete",
        json={"ids": [exp2.json()["export_id"]]},
        headers=officer_hdrs,
    )
    assert bdel_exp.status_code == 200
    assert bdel_exp.json()["deleted_count"] == 1

    # Single + batch delete applicants (officer deleting own applicants)
    assert client.delete(f"/api/applicants/{created_apps[0]}", headers=officer_hdrs).status_code == 200
    bdel_apps = client.post(
        "/api/applicants/batch-delete",
        json={"ids": [created_apps[1]]},
        headers=officer_hdrs,
    )
    assert bdel_apps.status_code == 200
    assert bdel_apps.json()["deleted_count"] == 1

    # 2. Create & delete custom document types and requirement sets
    dt1 = client.post(
        "/api/requirements/document-types",
        json={"name": "Custom Temp Doc 1", "code": "CUSTOM_TEMP_1", "aliases": ["Temp1"]},
        headers=super_hdrs,
    )
    dt2 = client.post(
        "/api/requirements/document-types",
        json={"name": "Custom Temp Doc 2", "code": "CUSTOM_TEMP_2", "aliases": ["Temp2"]},
        headers=super_hdrs,
    )
    assert dt1.status_code == 201 and dt2.status_code == 201

    rs1 = client.post(
        "/api/requirements",
        json={
            "name": "Temp Checklist 1",
            "destination_id": dests["MT"]["id"],
            "purpose_id": purps["WORK"]["id"],
            "category_id": cats["SKILLED_WORKER"]["id"],
            "items": [{"document_type_id": dt1.json()["id"], "requirement_level": "REQUIRED", "display_order": 1}],
        },
        headers=super_hdrs,
    )
    rs2 = client.post(
        "/api/requirements",
        json={
            "name": "Temp Checklist 2",
            "destination_id": dests["FR"]["id"],
            "purpose_id": purps["WORK"]["id"],
            "category_id": cats["SKILLED_WORKER"]["id"],
            "items": [{"document_type_id": dt2.json()["id"], "requirement_level": "REQUIRED", "display_order": 1}],
        },
        headers=super_hdrs,
    )
    assert rs1.status_code == 201 and rs2.status_code == 201
    assert client.delete(f"/api/requirements/{rs1.json()['id']}", headers=super_hdrs).status_code == 200
    assert (
        client.post(
            "/api/requirements/batch-delete",
            json={"ids": [rs2.json()["id"]]},
            headers=super_hdrs,
        ).json()["deleted_count"]
        == 1
    )
    assert (
        client.delete(
            f"/api/requirements/document-types/{dt1.json()['id']}", headers=super_hdrs
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/requirements/document-types/batch-delete",
            json={"ids": [dt2.json()["id"]]},
            headers=super_hdrs,
        ).json()["deleted_count"]
        == 1
    )

    # 3. Create & delete staff users (single + batch), blocking self-delete
    u1 = client.post(
        "/api/users",
        json={"first_name": "Temp", "last_name": "One", "password": "TempPass1"},
        headers=super_hdrs,
    )
    u2 = client.post(
        "/api/users",
        json={"first_name": "Temp", "last_name": "Two", "password": "TempPass2"},
        headers=super_hdrs,
    )
    assert u1.status_code == 201 and u2.status_code == 201
    assert client.delete(f"/api/users/{u1.json()['id']}", headers=super_hdrs).status_code == 200
    bdel_u = client.post(
        "/api/users/batch-delete",
        json={"ids": [u2.json()["id"]]},
        headers=super_hdrs,
    )
    assert bdel_u.status_code == 200
    assert bdel_u.json()["deleted_count"] == 1
    me_super = client.get("/api/auth/me", headers=super_hdrs).json()
    assert client.delete(f"/api/users/{me_super['id']}", headers=super_hdrs).status_code == 400
