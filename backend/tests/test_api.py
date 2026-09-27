"""API tests against the offline demo data (header X-Demo-Mode: 1)."""

import pytest
from fastapi.testclient import TestClient

from app.core.datasource import DataSource, FallbackSource, demo_source, get_datasource
from app.main import app

client = TestClient(app, headers={"X-Demo-Mode": "1"})


def _ids():
    block = next(b for b in client.get("/api/regions/blocks").json() if b["name"] == "Gajwel")
    gps = client.get(f"/api/blocks/{block['id']}/panchayats/geojson?var=rain&day=2").json()["features"]
    ahmadipur = next(f for f in gps if f["properties"]["name"] == "Ahmadipur")
    return block["id"], ahmadipur["id"]


BLOCK, AHMADIPUR = _ids()


def test_health():
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["serving"] == "demo"


def test_regions_cascade():
    states = client.get("/api/regions/states").json()
    assert states[0]["name"] == "Telangana"
    districts = client.get(f"/api/regions/districts?state={states[0]['id']}").json()
    assert districts[0]["name"] == "Siddipet"
    blocks = client.get(f"/api/regions/blocks?district={districts[0]['id']}").json()
    assert "Gajwel" in [b["name"] for b in blocks]
    gj = client.get(f"/api/regions/districts/{districts[0]['id']}/geojson").json()
    assert len(gj["features"]) == 1 + len(blocks)


def test_data_source_header():
    res = client.get("/api/regions/states")
    assert res.headers["X-Data-Source"] == "demo"
    assert "X-Data-Stale" not in res.headers


def test_summary():
    s = client.get(f"/api/blocks/{BLOCK}/summary").json()
    assert s["panchayat_count"] == 24
    assert s["run"]["source_label"]
    assert len(s["days"]) == 5
    assert s["active_alerts"] == len(s["alerts"]) >= 1


def test_geojson_24_features_and_block_value():
    fc = client.get(f"/api/blocks/{BLOCK}/panchayats/geojson?var=rain&day=2").json()
    assert len(fc["features"]) == 24
    assert fc["meta"]["block_value"] == 8.0
    vals = [f["properties"]["value"] for f in fc["features"]]
    assert sum(vals) / len(vals) == pytest.approx(8.0, abs=0.01)  # mass consistency via the API
    assert client.get(f"/api/blocks/{BLOCK}/geojson").json()["features"][0]["geometry"]["type"] == "MultiPolygon"


@pytest.mark.parametrize("var", ["rain", "tmax", "tmin", "rh", "wind"])
@pytest.mark.parametrize("day", [1, 2, 3, 4, 5])
def test_mass_consistency_all_vars(var, day):
    fc = client.get(f"/api/blocks/{BLOCK}/panchayats/geojson?var={var}&day={day}").json()
    vals = [f["properties"]["value"] for f in fc["features"]]
    assert sum(vals) / len(vals) == pytest.approx(fc["meta"]["block_value"], abs=0.05)


def test_insight_text():
    ins = client.get(f"/api/blocks/{BLOCK}/insight?var=rain&day=2").json()
    assert ins["text"] == "Rain varies 0-38 mm across 24 GPs; block says 8 mm"


def test_bad_day_rejected():
    assert client.get(f"/api/blocks/{BLOCK}/insight?var=rain&day=9").status_code == 422


def test_block_forecast():
    body = client.get(f"/api/forecast/block/{BLOCK}?day=2").json()
    assert body["days"][0]["rain_mm"] == 8.0
    assert body["days"][0]["rain_category"]["label"] == "Light rain"


def test_panchayat_detail_ahmadipur():
    body = client.get(f"/api/forecast/panchayat/{AHMADIPUR}").json()
    d2 = body["days"][1]
    assert (d2["rain_mm"], d2["rain_prob_10mm"], d2["confidence"]) == (38.0, 0.72, "high")
    assert d2["diff"]["rain_mm"] == 30.0
    assert d2["weekday"] == "Tue"
    assert any(a["day"] == 2 and a["type"] == "rain" for a in body["alerts"])
    assert body["panchayat"]["confidence"] == "high"


def test_404s():
    assert client.get("/api/forecast/panchayat/9999").status_code == 404
    assert client.get("/api/blocks/9999/summary").status_code == 404


def test_advisory_approve_share_flow():
    adv = client.post("/api/advisory/generate",
                      json={"panchayat_id": AHMADIPUR, "crop": "cotton", "stage": "square_formation"}).json()
    assert adv["status"] == "draft"
    # Sending a draft is refused
    assert client.post("/api/share", json={"advisory_id": adv["id"], "channel": "sms", "language": "te"}).status_code == 409
    edited = client.patch(f"/api/advisory/{adv['id']}", json={"edited_text": {"te": "test"}}).json()
    assert edited["edited_text"] == {"te": "test"}
    assert client.post(f"/api/advisory/{adv['id']}/approve").json()["status"] == "approved"
    sent = client.post("/api/share", json={"advisory_id": adv["id"], "channel": "whatsapp", "language": "te"}).json()
    assert sent["recipients"] == 312 and sent["status"] == "Delivered (simulated)"
    log = client.get(f"/api/share/log?advisory_id={adv['id']}").json()
    assert log[0]["id"] == sent["id"]
    pub = client.get(f"/api/public/panchayat/{AHMADIPUR}?lang=te").json()
    assert pub["advisory"]["id"] == adv["id"]


def test_validation_flags_placeholders():
    body = client.get("/api/validation").json()
    assert body["is_placeholder"] is True
    tmax = next(m for m in body["metrics"] if m["variable"] == "tmax")
    assert tmax["change_pct"]["rmse"] < 0
    assert body["backtest_events"][0]["station_name"]
    assert not any(s["used_in_training"] for s in body["stations"])


def test_feedback_and_public_page():
    assert client.post("/api/feedback/rain", json={"panchayat_id": AHMADIPUR, "rained": True}).status_code == 201
    pub = client.get(f"/api/public/panchayat/{AHMADIPUR}?lang=te").json()
    assert pub["panchayat"]["name"] == "అహ్మదీపూర్"
    assert pub["confidence"]["level"] == "high"
    assert len(pub["days"]) == 5


def test_officer_required_without_demo():
    plain = TestClient(app)
    from app.core import auth

    # Simulate a configured server (not in demo): no token -> 401
    orig = auth.use_demo
    auth.use_demo = lambda request=None: False
    try:
        res = plain.post("/api/advisory/generate",
                         json={"panchayat_id": AHMADIPUR, "crop": "cotton", "stage": "sowing"})
        assert res.status_code == 401
    finally:
        auth.use_demo = orig


class _Broken(DataSource):
    name = "supabase"

    def __getattribute__(self, item):
        if item == "name":
            return "supabase"

        def boom(*a, **k):
            raise ConnectionError("network down")

        return boom


def test_fallback_serves_demo_and_marks_stale():
    app.dependency_overrides[get_datasource] = lambda: FallbackSource(_Broken(), demo_source())
    try:
        res = TestClient(app).get(f"/api/blocks/{BLOCK}/insight?var=rain&day=2")
        assert res.status_code == 200
        assert res.headers.get("X-Data-Stale") == "1"
        assert res.json()["text"].startswith("Rain varies 0-38 mm")
    finally:
        app.dependency_overrides.clear()


def test_forecast_bundle_for_split_map():
    res = client.get(f"/api/blocks/{BLOCK}/panchayats/forecast")
    body = res.json()
    assert len(body["features"]) == 24
    assert body["meta"]["block_geometry"]["type"] == "MultiPolygon"
    assert [d["day"] for d in body["meta"]["days"]] == [1, 2, 3, 4, 5]
    bv = body["meta"]["block_values"][1]
    assert bv["rain"] == 8.0 and bv["tmax"] == 30.0
    for var in ("rain", "tmax", "tmin", "rh", "wind"):
        for day in range(5):
            vals = [f["properties"]["days"][day][var] for f in body["features"]]
            assert sum(vals) / len(vals) == pytest.approx(body["meta"]["block_values"][day][var], abs=0.05)
    assert len(res.content) < 150_000
