"""Advisory rule engine tests (demo data)."""

import copy

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.datasource import demo_source
from app.main import app
from app.services import advisory as engine
from app.services.forecast import panchayat_forecast

client = TestClient(app, headers={"X-Demo-Mode": "1"})


def _gp_id(name: str) -> int:
    return next(p["id"] for p in demo_source().list_panchayats(1) if p["name"] == name)


AHMADIPUR = _gp_id("Ahmadipur")


def _days(gp_id: int) -> tuple[list[dict], str]:
    fc = panchayat_forecast(demo_source(), gp_id)
    return fc["days"], fc["panchayat"]["confidence"]


def test_ahmadipur_cotton_square_formation_matches_demo_script():
    days, conf = _days(AHMADIPUR)
    items = engine.evaluate(days, "cotton", "square_formation", conf)
    assert [i["id"] for i in items[:3]] == ["spray_postpone", "drains_prepare", "urea_now"]
    assert [i["tag"] for i in items[:3]] == ["avoid", "prepare", "do_now"]
    spray, drains, urea = items[:3]
    assert spray["title"]["en"] == "Postpone pesticide spray until Thursday"
    assert "72% chance of more than 10 mm" in spray["reason"]["en"]
    assert drains["title"]["en"] == "Clear field drains before Tuesday"
    assert "38 mm" in drains["reason"]["en"]
    assert "గురువారం" in spray["title"]["te"] and "गुरुवार" in spray["title"]["hi"]


def test_explain_shows_threshold_and_actual():
    days, conf = _days(AHMADIPUR)
    spray = engine.evaluate(days, "cotton", "square_formation", conf)[0]
    cond = spray["explain"]["conditions"][0]
    assert (cond["metric"], cond["op"], cond["threshold"], cond["actual"], cond["unit"]) == (
        "p10_48h", ">=", 60.0, 72.0, "%")
    assert [d["day"] for d in spray["explain"]["days_used"]] == [1, 2]


def test_paddy_gets_bunds_not_drains():
    days, conf = _days(AHMADIPUR)
    ids = [i["id"] for i in engine.evaluate(days, "paddy", "transplanting_tillering", conf)]
    assert "bunds_prepare" in ids and "drains_prepare" not in ids


def test_heavy_rain_swaps_urea_for_fertilizer_postpone():
    days, conf = _days(AHMADIPUR)
    wet = copy.deepcopy(days)
    wet[0]["rain_mm"] = 40.0
    wet[1]["rain_mm"] = 45.0
    ids = [i["id"] for i in engine.evaluate(wet, "cotton", "square_formation", conf)]
    assert "fertilizer_postpone" in ids and "urea_now" not in ids


def test_low_confidence_adds_cautious_fallback():
    days, _ = _days(AHMADIPUR)
    items = engine.evaluate(days, "maize", "vegetative", "low")
    assert any(i["id"] == "low_confidence" for i in items)


def test_harvest_stage_skips_spray_advice():
    days, conf = _days(AHMADIPUR)
    ids = [i["id"] for i in engine.evaluate(days, "cotton", "picking", conf)]
    assert "spray_postpone" not in ids and "harvest_postpone" in ids


def test_every_rule_has_all_languages():
    for rule in engine.load_rules()["rules"]:
        for part in ("title", "reason"):
            assert set(rule[part]) == {"en", "te", "hi"}, (rule["id"], part)


def test_unknown_stage_rejected():
    with pytest.raises(HTTPException):
        engine.validate("cotton", "tillering")


def test_generate_endpoint_and_crops():
    crops = client.get("/api/advisory/crops").json()
    assert {c["id"] for c in crops} == {"cotton", "paddy", "maize"}
    res = client.post("/api/advisory/generate",
                      json={"panchayat_id": AHMADIPUR, "crop": "cotton", "stage": "square_formation"})
    assert res.status_code == 200
    body = res.json()
    assert body["items"][0]["id"] == "spray_postpone" and body["status"] == "draft"
    bad = client.post("/api/advisory/generate", json={"panchayat_id": AHMADIPUR, "crop": "cotton", "stage": "x"})
    assert bad.status_code == 422
