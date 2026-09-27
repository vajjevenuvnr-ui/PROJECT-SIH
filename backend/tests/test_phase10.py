"""Phase 10: crop profiles -> stage, change notifications, bulletin PDF, bulk dispatch, feedback summary, false onset."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.datasource import demo_source
from app.main import app
from app.services.advisory import evaluate, stage_for
from app.services.profiles import resolve

client = TestClient(app, headers={"X-Demo-Mode": "1"})


@pytest.fixture(autouse=True)
def _reset_simulation():
    demo_source().reset_simulation()
    yield
    demo_source().reset_simulation()


def test_stage_from_sowing_date():
    assert stage_for("cotton", date(2025, 6, 1), date(2025, 6, 10))[0] == "sowing"
    assert stage_for("cotton", date(2025, 6, 1), date(2025, 7, 25)) == ("square_formation", 54)
    assert stage_for("paddy", date(2025, 6, 1), date(2025, 12, 1))[0] == "harvest"


def test_default_profile_for_demo_gp():
    p = resolve(None, 7, date(2025, 9, 13))
    assert p["crop"] == "cotton" and p["is_default"] and p["stage"] and p["days_since_sowing"] >= 40


def test_profile_api_and_put():
    r = client.get("/api/crop-profiles/7")
    assert r.status_code == 200 and {"crop", "stage", "stage_name", "sowing_date"} <= r.json().keys()
    assert len(client.get("/api/crop-profiles?block_id=1").json()) == 24
    r = client.put("/api/crop-profiles/7", json={"crop": "paddy", "sowing_date": "2025-06-01"})
    assert r.status_code == 200 and r.json()["crop"] == "paddy" and not r.json()["is_default"]
    assert client.put("/api/crop-profiles/7", json={"crop": "banana", "sowing_date": "2025-06-01"}).status_code == 422
    demo_source()._profiles.pop(7, None)


def test_changes_after_simulation():
    assert client.get("/api/alerts/changes?block_id=1").status_code == 200
    client.post("/api/demo/simulate-extreme", json={})
    ch = client.get("/api/alerts/changes?block_id=1").json()["changes"]
    assert ch and all({"en", "te", "hi"} <= c["text"].keys() for c in ch)
    assert {"rain", "alert"} & {c["kind"] for c in ch}


def test_bulletin_pdf():
    r = client.get("/api/blocks/1/bulletin.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"


def test_bulk_generate_and_send():
    drafts = client.post("/api/advisory/generate-bulk", json={"block_id": 1}).json()
    assert len(drafts) == 24 and all(d["advisory"]["status"] == "draft" for d in drafts)
    ids = [d["advisory"]["id"] for d in drafts[:3]]
    r = client.post("/api/advisory/send-bulk", json={"advisory_ids": ids, "channel": "sms", "language": "te"}).json()
    assert r["sent"] == 3 and r["farmers"] >= 0


def test_feedback_summary():
    r = client.get("/api/feedback/summary?block_id=1")
    assert r.status_code == 200 and {"reports", "agreement", "rows"} <= r.json().keys()


def test_false_onset_blocks_sowing():
    days = [{"day": i, "date": f"2025-07-0{i}", "weekday": "", "rain_mm": 15.0 if i < 3 else 0.0, "rain_prob": 0.8,
             "tmax": 32, "tmin": 24, "rh_max": 85, "rh_min": 60, "wind_kmh": 8, "confidence": "high"} for i in range(1, 6)]
    ids = {i["id"] for i in evaluate(days, "cotton", "sowing", "high")}
    assert "sowing_go" not in ids or "false_onset" in ids
