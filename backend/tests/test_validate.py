"""Validation scoring (no network): metrics, bootstrap CI, backtest selection, honest counts."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from pipeline.validate import compute


def _synthetic(n=200, seed=1):
    rng = np.random.default_rng(seed)
    obs_t = 30 + rng.normal(0, 2, n)
    obs_r = np.where(rng.random(n) < 0.4, rng.gamma(1.2, 15, n), 0.0)
    return pd.DataFrame({
        "station_id": np.repeat(["A", "B"], n // 2), "date": [f"2024-07-{(i % 28) + 1:02d}" for i in range(n)],
        "obs_tmax": obs_t, "obs_tmin": obs_t - 8, "obs_rain": obs_r,
        "block_tmax": obs_t + rng.normal(1.0, 1.5, n), "block_tmin": obs_t - 8 + rng.normal(0.5, 1.0, n),
        "block_rain": np.maximum(obs_r * 0.4 + rng.normal(3, 4, n), 0),
        # "ours" is closer to the truth by construction
        "ours_tmax": obs_t + rng.normal(0.2, 0.6, n), "ours_tmin": obs_t - 8 + rng.normal(0.1, 0.4, n),
        "ours_rain": np.maximum(obs_r * 0.9 + rng.normal(0.5, 1.5, n), 0),
    })


def test_compute_detects_a_real_improvement():
    df = _synthetic()
    stations = pd.DataFrame({"station_id": ["A", "B"], "name": ["Alpha", "Beta"]})
    res = compute(df, stations)
    t = res["improvements"]["tmax"]
    assert t["change_pct"] < -40 and t["ci90"][1] < 0  # whole CI better
    base = next(m for m in res["metrics"] if m["variable"] == "rain" and m["threshold_mm"] == 10 and m["method"] == "block_baseline")
    ours = next(m for m in res["metrics"] if m["variable"] == "rain" and m["threshold_mm"] == 10 and m["method"] == "panchayatcast")
    assert ours["csi"] > base["csi"] and ours["n_events"] == base["n_events"] > 5
    assert res["backtest_events"] and res["backtest_events"][0]["station_name"] in ("Alpha", "Beta")
    c = res["wet_day_counts"]
    assert c["better"] + c["worse"] + c["similar"] == c["wet_days"]
    assert not any(m["is_placeholder"] for m in res["metrics"])


def test_rare_threshold_not_scored():
    df = _synthetic()
    df["obs_rain"] = np.minimum(df["obs_rain"], 60)  # no event >= 64.5 mm
    res = compute(df, pd.DataFrame({"station_id": ["A", "B"], "name": ["A", "B"]}))
    assert not any(m["threshold_mm"] == 64.5 for m in res["metrics"])


def test_endpoint_on_seed_is_placeholder():
    client = TestClient(app, headers={"X-Demo-Mode": "1"})
    body = client.get("/api/validation").json()
    assert body["is_placeholder"] is True and body["summary"] is None
    assert client.get("/api/validation/station/nope/series").status_code == 404
