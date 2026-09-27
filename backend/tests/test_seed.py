"""Checks on the deterministic demo seed (no database needed)."""

import json

import pytest

from scripts.seed_demo import SEED_DIR, build_dataset, build_seed_sql, check_dataset


@pytest.fixture(scope="module")
def ds():
    return build_dataset()


def test_all_checks_pass(ds):
    check_dataset(ds)  # raises AssertionError on failure


def test_mass_consistency_rain_day2(ds):
    gajwel = {g["id"] for g in ds.panchayats if g["block_id"] == 1}
    rows = [r for r in ds.panchayat_forecasts if r["day"] == 2 and r["panchayat_id"] in gajwel]
    assert len(rows) == 24
    assert sum(r["rain_mm"] for r in rows) / 24 == pytest.approx(8.0, abs=0.01)


def test_ahmadipur_demo_values(ds):
    gp = next(g for g in ds.panchayats if g["name"] == "Ahmadipur")
    assert gp["registered_farmers"] == 312
    d2 = next(r for r in ds.panchayat_forecasts if r["panchayat_id"] == gp["id"] and r["day"] == 2)
    assert (d2["rain_mm"], d2["rain_prob_10mm"], d2["confidence"]) == (38.0, 0.72, "high")


def test_higher_gps_are_cooler(ds):
    rows = {r["panchayat_id"]: r for r in ds.panchayat_forecasts if r["day"] == 4}
    hi = max(ds.panchayats, key=lambda g: g["elevation_m"])
    lo = min(ds.panchayats, key=lambda g: g["elevation_m"])
    assert rows[hi["id"]]["tmax"] < rows[lo["id"]]["tmax"]


def test_deterministic(ds):
    assert build_seed_sql(build_dataset()) == build_seed_sql(ds)


def test_stations_held_out(ds):
    assert ds.aws_stations and not any(s["used_in_training"] for s in ds.aws_stations)


def test_placeholders_are_flagged(ds):
    assert all(m["is_placeholder"] for m in ds.validation_metrics)
    assert all(e["is_placeholder"] for e in ds.backtest_events)


def test_demo_json_written():
    fc = json.loads((SEED_DIR / "forecast.json").read_text(encoding="utf-8"))
    assert len(fc["panchayat_forecasts"]) == 290 * 5  # all 8 Siddipet blocks (Phase 10)
