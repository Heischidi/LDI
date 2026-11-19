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
