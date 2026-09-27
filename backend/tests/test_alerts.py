"""Extreme-weather alerts: IMD colour levels, siren gating, simulation, dispatch, CAP, push subscriptions."""

from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.api import alerts as alerts_api
from app.core.datasource import demo_source
from app.main import app
from app.services.warnings import warnings_for_day

client = TestClient(app, headers={"X-Demo-Mode": "1"})
AHMADIPUR = next(p["id"] for p in demo_source().list_panchayats(1) if p["name"] == "Ahmadipur")
CAP = "{urn:oasis:names:tc:emergency:cap:1.2}"


@pytest.fixture(autouse=True)
def _reset_simulation():
    demo_source().reset_simulation()
    yield
    demo_source().reset_simulation()


def _row(rain=0.0, tmax=32.0, wind=10.0, conf="high"):
    return {"day": 2, "date": "2026-07-21", "rain_mm": rain, "tmax": tmax, "wind_kmh": wind,
            "rain_prob_10mm": 0.9, "confidence": conf}


GP = {"id": 1, "name": "Test", "name_te": "టెస్ట్", "name_hi": None, "registered_farmers": 10}
RUN = {"id": 1, "source": "seed"}


@pytest.mark.parametrize("rain,level", [(60, None), (64.5, "yellow"), (115.6, "orange"), (204.5, "red")])
def test_imd_rain_thresholds(rain, level):
    ws = [w for w in warnings_for_day(_row(rain=rain), GP, RUN) if w["hazard"] == "rain"]
    assert (ws[0]["level"] if ws else None) == level


def test_siren_only_orange_red_with_confidence():
    assert warnings_for_day(_row(rain=120, conf="high"), GP, RUN)[0]["siren"] is True
    assert warnings_for_day(_row(rain=120, conf="low"), GP, RUN)[0]["siren"] is False
    assert warnings_for_day(_row(rain=70, conf="high"), GP, RUN)[0]["siren"] is False  # yellow: banner only


def test_texts_in_three_languages():
    w = warnings_for_day(_row(rain=130), GP, RUN)[0]
    assert w["title"]["en"] == "ORANGE alert · Very heavy rain"
    assert "నారింజ" in w["title"]["te"] and "नारंगी" in w["title"]["hi"]
    assert len(w["actions"]["te"]) == 3


def test_no_warnings_in_seed_then_simulation_creates_them():
    assert client.get("/api/alerts", params={"block_id": 1}).json()["alerts"] == []
    sim = client.post("/api/demo/simulate-extreme", json={}).json()
    assert sim["center_panchayat_id"] == AHMADIPUR and sim["active"]
    body = client.get("/api/alerts", params={"block_id": 1}).json()
    top = body["alerts"][0]
    assert (top["panchayat_id"], top["level"], top["value"], top["siren"]) == (AHMADIPUR, "orange", 132.0, True)
    assert body["simulation"]["center"] == AHMADIPUR
    assert all(w["simulated"] for w in body["alerts"])
    assert len(client.get("/api/alerts", params={"block_id": 1, "min_level": "orange"}).json()["alerts"]) == 2


def test_simulation_keeps_mass_consistency_and_is_labelled():
    client.post("/api/demo/simulate-extreme", json={})
    fc = client.get("/api/blocks/1/panchayats/forecast").json()
    vals = [f["properties"]["days"][1]["rain"] for f in fc["features"]]
    assert sum(vals) / len(vals) == pytest.approx(fc["meta"]["block_values"][1]["rain"], abs=0.05)
    assert fc["meta"]["run"]["source"] == "simulated"


def test_ack_dispatch_and_log(monkeypatch):
    client.post("/api/demo/simulate-extreme", json={})
    alert_id = client.get("/api/alerts", params={"block_id": 1}).json()["alerts"][0]["id"]
    # one subscribed phone; push delivery mocked
    client.post("/api/push/subscribe", json={"panchayat_id": AHMADIPUR, "lang": "te",
                                             "subscription": {"endpoint": "https://push.example/abc",
                                                              "keys": {"p256dh": "k", "auth": "a"}}})
    sent = []
    monkeypatch.setattr(alerts_api, "push_enabled", lambda: True)
    monkeypatch.setattr(alerts_api, "send_push",
                        lambda subs, payload: sent.extend(payload(s) for s in subs) or
                        {"sent": len(subs), "failed": 0, "expired": []})
    res = client.post(f"/api/alerts/{alert_id}/dispatch").json()
    assert res["push"]["sent"] == 1
    assert sent[0]["url"] == f"/f/{AHMADIPUR}?lang=te&sos=1" and "నారింజ" in sent[0]["title"]
    channels = {r["channel"]: r for r in client.get("/api/alerts/log", params={"alert_id": alert_id}).json()}
    assert channels["sms_alert"]["recipients"] == 312 and "simulated" in channels["voice_alert"]["status"].lower()
    assert client.post(f"/api/alerts/{alert_id}/ack").status_code == 200
    assert alert_id in client.get("/api/alerts", params={"block_id": 1}).json()["acknowledged"]
    client.post("/api/push/unsubscribe", json={"endpoint": "https://push.example/abc"})


def test_cap_xml_is_valid_and_marked_exercise():
    client.post("/api/demo/simulate-extreme", json={})
    alert_id = client.get("/api/alerts", params={"block_id": 1}).json()["alerts"][0]["id"]
    res = client.get(f"/api/alerts/{alert_id}/cap")
    assert res.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(res.content)
    assert root.find(f"{CAP}status").text == "Exercise"
    infos = root.findall(f"{CAP}info")
    assert [i.find(f"{CAP}language").text for i in infos] == ["en-IN", "te-IN", "hi-IN"]
    assert infos[0].find(f"{CAP}severity").text == "Severe"
    poly = infos[0].find(f"{CAP}area/{CAP}polygon").text.split()
    assert poly[0] == poly[-1] and len(poly) >= 4


def test_reset_and_stale_alert_404():
    client.post("/api/demo/simulate-extreme", json={})
    alert_id = client.get("/api/alerts", params={"block_id": 1}).json()["alerts"][0]["id"]
    client.post("/api/demo/reset-simulation")
    assert client.get("/api/alerts", params={"block_id": 1}).json()["alerts"] == []
    assert client.get(f"/api/alerts/{alert_id}/cap").status_code == 404


def test_public_page_and_s3_carry_warnings():
    client.post("/api/demo/simulate-extreme", json={})
    pub = client.get(f"/api/public/panchayat/{AHMADIPUR}", params={"lang": "te"}).json()
    assert pub["warnings"][0]["level"] == "orange" and isinstance(pub["warnings"][0]["actions"], list)
    s3 = client.get(f"/api/forecast/panchayat/{AHMADIPUR}").json()
    assert s3["warnings"][0]["value"] == 132.0
    summary = client.get("/api/blocks/1/summary").json()
    assert len(summary["warnings"]) == 5


def test_push_subscribe_validation():
    bad = client.post("/api/push/subscribe", json={"panchayat_id": AHMADIPUR, "subscription": {
        "endpoint": "http://insecure", "keys": {"p256dh": "k", "auth": "a"}}})
    assert bad.status_code == 422
    assert "enabled" in client.get("/api/push/public-key").json()
