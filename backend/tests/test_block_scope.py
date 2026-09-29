"""An officer can send, approve and edit only in their assigned blocks; viewing stays open."""

import pytest
from fastapi.testclient import TestClient

from app.core.auth import Officer, require_officer
from app.core.datasource import demo_source
from app.main import app

client = TestClient(app, headers={"X-Demo-Mode": "1"})
GAJWEL_GP = 7
OTHER_GP = demo_source().list_panchayats(3)[0]["id"]  # a Mulugu panchayat


@pytest.fixture(autouse=True)
def lakshmi():
    app.dependency_overrides[require_officer] = lambda: Officer(id=None, name="Lakshmi", role="officer", block_ids=(1,))
    yield
    app.dependency_overrides.clear()


def _gen(gp):
    return client.post("/api/advisory/generate", json={"panchayat_id": gp, "crop": "cotton", "stage": "square_formation", "lang": "te"})


def test_generate_and_send_only_in_own_block():
    assert _gen(OTHER_GP).status_code == 403
    adv = _gen(GAJWEL_GP).json()
    assert client.post(f"/api/advisory/{adv['id']}/approve").status_code == 200
    assert client.post("/api/share", json={"advisory_id": adv["id"], "channel": "sms", "language": "te"}).status_code == 200


def test_bulk_is_scoped_and_all_or_nothing():
    assert client.post("/api/advisory/generate-bulk", json={"block_id": 3}).status_code == 403
    mine = client.post("/api/advisory/generate-bulk", json={"block_id": 1}).json()[0]["advisory"]["id"]
    app.dependency_overrides.clear()  # demo officer (all blocks) drafts one elsewhere
    other = _gen(OTHER_GP).json()["id"]
    app.dependency_overrides[require_officer] = lambda: Officer(id=None, name="Lakshmi", role="officer", block_ids=(1,))
    r = client.post("/api/advisory/send-bulk", json={"advisory_ids": [mine, other], "channel": "sms", "language": "te"})
    assert r.status_code == 403
    assert demo_source().get_advisory(mine)["status"] == "draft"  # nothing was sent


def test_other_block_edits_refused_but_viewing_open():
    assert client.put(f"/api/crop-profiles/{OTHER_GP}", json={"crop": "cotton", "sowing_date": "2025-06-20"}).status_code == 403
    assert client.get("/api/blocks/3/summary").status_code == 200
    assert client.get(f"/api/forecast/panchayat/{OTHER_GP}").status_code == 200
    assert client.get("/api/farmers?block_id=3").status_code == 403
