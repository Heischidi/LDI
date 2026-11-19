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
