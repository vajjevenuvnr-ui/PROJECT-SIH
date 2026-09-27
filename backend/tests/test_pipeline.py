"""Pipeline unit tests: pure maths and geometry (no network, no trained models needed)."""

import numpy as np
import pytest

from pipeline.downscale import additive, es, multiplicative, round_keep_mean
from pipeline.grid import cells_for_block, forecast_points, load_block
from pipeline.ingest import Feed, block_bulletin
from pipeline.run_daily import check
from pipeline.train import bilinear_weights, categorical, idw, interp, quantile_map


def test_mass_consistency_additive_and_multiplicative():
    v = np.array([28.0, 30.0, 32.0])
    assert additive(v, 31.0).mean() == pytest.approx(31.0)
    r = multiplicative(np.array([0.0, 10.0, 20.0]), 8.0)
    assert r.mean() == pytest.approx(8.0) and r[0] == 0.0  # dry stays dry, pattern kept
    assert multiplicative(np.zeros(3), 5.0).tolist() == [5.0, 5.0, 5.0]  # no pattern: uniform
    assert multiplicative(np.array([3.0, 4.0]), 0.0).tolist() == [0.0, 0.0]


def test_round_keep_mean_exact():
    v = round_keep_mean(np.array([0.04, 7.33, 12.62, 21.97]), 10.49, floor=0.0)
    assert round(v.mean(), 2) == pytest.approx(10.5, abs=0.001) and (v >= 0).all()


def test_saturation_vapour_pressure():
    assert es(np.array(0.0)) == pytest.approx(6.112, rel=1e-3)
    assert es(np.array(30.0)) == pytest.approx(42.4, rel=0.01)


def test_bilinear_interp_and_idw():
    glat, glon = np.array([17.5, 17.75]), np.array([78.5, 78.75])
    field = np.array([[0.0, 10.0], [20.0, 30.0]])
    w = bilinear_weights(glat, glon, np.array([17.625]), np.array([78.625]))
    assert interp(field, w)[0] == pytest.approx(15.0)
    assert idw(np.array([0.0, 1.0]), np.array([0.0, 0.0]), np.array([10.0, 20.0]), np.array([0.0]), np.array([0.0]))[0] \
        == pytest.approx(10.0, abs=1e-3)


def test_categorical_scores():
    obs = np.array([1, 1, 0, 0, 1], dtype=bool)
    fc = np.array([1, 0, 1, 0, 1], dtype=bool)
    s = categorical(obs, fc)
    assert (s["hits"], s["misses"], s["false_alarms"]) == (2, 1, 1)
    assert s["pod"] == pytest.approx(0.667, abs=1e-3) and s["csi"] == 0.5


def test_quantile_mapping_monotone():
    out = quantile_map(np.array([0.0, 5.0, 10.0]), [0.0, 10.0], [0.0, 40.0])
    assert out.tolist() == [0.0, 20.0, 40.0]


def test_grid_covers_every_panchayat():
    block, gps = load_block(1)
    cells = cells_for_block(block, gps, 1.0)
    assert set(cells["gp_id"]) == {g["id"] for g in gps}
    assert 300 < len(cells) < 700
    assert len(forecast_points(block, 8)) >= 4


def _fake_feed():
    n, d = 4, 5
    ones = np.ones((n, d))
    member = {"tmax": ones * 31, "tmin": ones * 23, "rain": np.tile([0, 8, 20, 1, 0], (n, 1)).astype(float),
              "rh_max": ones * 90, "rh_min": ones * 60, "wind_mean": ones * 12, "wind_max": ones * 20,
              "wind_dir": ones * 250, "cloud": ones * 75}
    return Feed(dates=[f"2024-08-0{i + 1}" for i in range(d)], lats=np.array([17.8, 17.8, 17.9, 17.9]),
                lons=np.array([78.6, 78.7, 78.6, 78.7]), members={"best_match": member}, stale=False,
                source="replay", official="best_match")


def test_block_bulletin_imd_fields():
    b = block_bulletin(_fake_feed())
    assert [x["rain_mm"] for x in b] == [0.0, 8.0, 20.0, 1.0, 0.0]
    assert b[0] | {} and set(b[0]) >= {"rain_mm", "tmax", "tmin", "rh_max", "rh_min", "wind_kmh", "wind_dir", "cloud_okta"}
    assert b[0]["cloud_okta"] == 6 and b[0]["wind_dir"] == 250


def test_check_rejects_inconsistent_run():
    out = {"block_forecasts": [{"day": 1, "rain_mm": 8.0, "tmax": 30.0, "tmin": 22.0, "wind_kmh": 10.0}],
           "panchayat_forecasts": [
               {"day": 1, "rain_mm": 0.0, "tmax": 30.0, "tmin": 22.0, "wind_kmh": 10.0},
               {"day": 1, "rain_mm": 30.0, "tmax": 30.0, "tmin": 22.0, "wind_kmh": 10.0}]}
    with pytest.raises(AssertionError, match="mass consistency"):
        check(out)
    out["panchayat_forecasts"][1]["rain_mm"] = 16.0
    check(out)
