"""Tests for authentication, token refresh/logout, account lockout, and strict RBAC."""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_login_refresh_logout_flow(client: TestClient):
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "officer@leaders.edu", "password": "LeadersOfficer!2026"},
    )
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["user"]["role"] == "OFFICER"
    access = body["access_token"]
    refresh = body["refresh_token"]

    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "officer@leaders.edu"

    # Refresh tokens
    ref_resp = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert ref_resp.status_code == 200
    new_access = ref_resp.json()["access_token"]

    # Logout revokes current access token
    logout_resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {new_access}"})
    assert logout_resp.status_code == 200

    blocked_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert blocked_resp.status_code == 401


def test_login_lockout_protection(client: TestClient):
    for _ in range(5):
        r = client.post(
            "/api/auth/login",
            json={"email": "viewer@leaders.edu", "password": "WrongPassword123"},
        )
        assert r.status_code == 401

    locked = client.post(
        "/api/auth/login",
        json={"email": "viewer@leaders.edu", "password": "LeadersViewer!2026"},
    )
    assert locked.status_code == 429
    assert "locked" in locked.json()["detail"].lower()


def test_rbac_enforcement(client: TestClient):
    viewer_hdrs = auth_headers(client, "viewer@leaders.edu", "LeadersViewer!2026")
    officer_hdrs = auth_headers(client, "officer@leaders.edu", "LeadersOfficer!2026")
    admin_hdrs = auth_headers(client, "admin@leaders.edu", "LeadersAdmin!2026")
    super_hdrs = auth_headers(client, "superadmin@leaders.edu", "LeadersAdmin!2026")

    # Viewer can read dashboard & applicants, cannot create applicant or view audit logs
    assert client.get("/api/dashboard/metrics", headers=viewer_hdrs).status_code == 200
    assert client.get("/api/applicants", headers=viewer_hdrs).status_code == 200
    assert client.get("/api/audit-logs", headers=viewer_hdrs).status_code == 403

    dests = client.get("/api/reference/destinations", headers=officer_hdrs).json()
    purposes = client.get("/api/reference/purposes", headers=officer_hdrs).json()
    cats = client.get("/api/reference/categories", headers=officer_hdrs).json()

    applicant_payload = {
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane.smith@example.com",
        "phone_number": "+2348011122233",
        "nationality": "Nigerian",
        "destination_id": dests[0]["id"],
        "purpose_id": purposes[0]["id"],
        "category_id": cats[0]["id"],
    }
    assert client.post("/api/applicants", json=applicant_payload, headers=viewer_hdrs).status_code == 403
    created = client.post("/api/applicants", json=applicant_payload, headers=officer_hdrs)
    assert created.status_code == 201

    # Officer cannot manage staff or settings or audit logs
    assert client.get("/api/users", headers=officer_hdrs).status_code == 403
    assert client.get("/api/settings", headers=officer_hdrs).status_code == 403
    assert client.get("/api/audit-logs", headers=officer_hdrs).status_code == 403

    # Admin can view audit logs & users, cannot update system settings
    assert client.get("/api/audit-logs", headers=admin_hdrs).status_code == 200
    assert client.get("/api/users", headers=admin_hdrs).status_code == 200
    assert (
        client.patch(
            "/api/settings/ai.provider",
            json={"value_json": {"provider": "LOCAL_DETERMINISTIC"}},
            headers=admin_hdrs,
        ).status_code
        == 403
    )

    # Super Admin can manage system settings and create/deactivate staff
    assert (
        client.patch(
            "/api/settings/ai.provider",
            json={"value_json": {"provider": "LOCAL_DETERMINISTIC", "allow_external_ai": False}},
            headers=super_hdrs,
        ).status_code
        == 200
    )
    new_staff = client.post(
        "/api/users",
        json={
            "email": "new.officer@leaders.edu",
            "password": "StrongPassword!2026",
            "first_name": "Kemi",
            "last_name": "Williams",
            "role_name": "OFFICER",
        },
        headers=super_hdrs,
    )
    assert new_staff.status_code == 201
    staff_id = new_staff.json()["id"]
    deact = client.patch(f"/api/users/{staff_id}", json={"is_active": False}, headers=super_hdrs)
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False


def test_officer_username_creation_login_and_client_isolation(client: TestClient):
    super_hdrs = auth_headers(client, "superadmin@leaders.edu", "LeadersAdmin!2026")

    # Super Admin creates two officers using only First Name, Last Name, and Password
    off1_resp = client.post(
        "/api/users",
        json={
            "first_name": "Chidi",
            "last_name": "Ejikonye",
            "password": "OfficerPass1",
        },
        headers=super_hdrs,
    )
    assert off1_resp.status_code == 201
    off1 = off1_resp.json()
    assert off1["username"] == "ejikonyech"
    assert off1["email"] == "ejikonyech@leaders.edu"
    assert off1["role"] == "OFFICER"

    off2_resp = client.post(
        "/api/users",
        json={
            "first_name": "Kemi",
            "last_name": "Balogun",
            "password": "OfficerPass2",
        },
        headers=super_hdrs,
    )
    assert off2_resp.status_code == 201
    assert off2_resp.json()["username"] == "balogunke"

    # Both officers log in using their auto-generated username + password
    login1 = client.post("/api/auth/login", json={"email": "ejikonyech", "password": "OfficerPass1"})
    assert login1.status_code == 200
    off1_hdrs = {"Authorization": f"Bearer {login1.json()['access_token']}"}

    login2 = client.post("/api/auth/login", json={"email": "balogunke", "password": "OfficerPass2"})
    assert login2.status_code == 200
    off2_hdrs = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    # Officer 1 creates a client
    dests = {d["code"]: d for d in client.get("/api/reference/destinations", headers=off1_hdrs).json()}
    purps = {p["code"]: p for p in client.get("/api/reference/purposes", headers=off1_hdrs).json()}
    cats = {c["code"]: c for c in client.get("/api/reference/categories", headers=off1_hdrs).json()}

    created = client.post(
        "/api/applicants",
        json={
            "first_name": "Ada",
            "last_name": "Nwachukwu",
            "email": "ada.nwachukwu@example.com",
            "phone_number": "+2348011112222",
            "nationality": "Nigerian",
            "destination_id": dests["CA"]["id"],
            "purpose_id": purps["STUDY"]["id"],
            "category_id": cats["STUDENT_VISA"]["id"],
        },
        headers=off1_hdrs,
    )
    assert created.status_code == 201
    applicant_id = created.json()["id"]

    # Officer 1 sees their own client
    list1 = client.get("/api/applicants", headers=off1_hdrs)
    assert list1.status_code == 200
    assert list1.json()["total"] == 1

    # Officer 2 cannot see or access Officer 1's client anywhere
    list2 = client.get("/api/applicants", headers=off2_hdrs)
    assert list2.status_code == 200
    assert list2.json()["total"] == 0

    docs2 = client.get("/api/documents", headers=off2_hdrs)
    assert docs2.status_code == 200
    assert docs2.json() == []

    assert client.get(f"/api/applicants/{applicant_id}", headers=off2_hdrs).status_code == 403
    assert client.get(f"/api/applicants/{applicant_id}/report", headers=off2_hdrs).status_code == 403
    assert client.post(f"/api/applicants/{applicant_id}/export", headers=off2_hdrs).status_code == 403
    assert (
        client.patch(
            f"/api/applicants/{applicant_id}",
            json={"nationality": "Ghanaian"},
            headers=off2_hdrs,
        ).status_code
        == 403
    )

    # Super Admin can change staff roles cleanly
    role_upd = client.patch(
        f"/api/users/{off2_resp.json()['id']}",
        json={"role_name": "ADMIN"},
        headers=super_hdrs,
    )
    assert role_upd.status_code == 200
    assert role_upd.json()["role"] == "ADMIN"

    # Super Admin can log in by username and see all officers' clients
    super_by_username = auth_headers(client, "superadmin", "LeadersAdmin!2026")
    assert super_by_username
    me_super = client.get("/api/auth/me", headers=super_by_username)
    assert me_super.status_code == 200
    assert me_super.json()["first_name"] == "Superadmin"
    assert me_super.json()["last_name"] == ""
    list_super = client.get("/api/applicants", headers=super_by_username)
    assert list_super.status_code == 200
    assert list_super.json()["total"] >= 1
    assert client.get(f"/api/applicants/{applicant_id}", headers=super_by_username).status_code == 200
