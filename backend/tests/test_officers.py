"""Officer accounts: only admins manage them; official email domains only."""

from fastapi.testclient import TestClient

from app.api.officers import allowed_email
from app.main import app

client = TestClient(app, headers={"X-Demo-Mode": "1"})


def test_allowed_email_domains():
    assert allowed_email("aeo@agri.telangana.gov.in") and allowed_email("x@nic.in")
    assert not allowed_email("someone@gmail.com") and not allowed_email("x@fakegov.in")


def test_me_and_demo_officer_is_not_admin():
    me = client.get("/api/me").json()
    assert me["role"] == "officer" and me["is_demo"]
    assert client.get("/api/officers").status_code == 403
    assert client.post("/api/officers/invite", json={"email": "a@nic.in", "name": "Aa", "block_ids": [1]}).status_code == 403
