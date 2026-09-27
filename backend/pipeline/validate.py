"""Validation against ground stations (Phase 8): does downscaling beat "copy the block value"?

For every station (never used in training):
  * a block-sized box (~30 km) around the station gets its block value from REAL archived forecasts
    (Open-Meteo Historical Forecast API, day-1, best_match) = mean of 3 x 3 model points  -> BASELINE
  * the trained engine downscales the same forecast to the station's exact location, with the same
    mass consistency against the box                                                           -> KSHETRA
  * both are scored against what the station recorded (daily, UTC days to match GSOD)

Scores: RMSE / MAE / bias for temperature; POD / FAR / CSI at IMD thresholds (2.5, 10, 64.5 mm) for rain;
bootstrap 90% confidence interval of the improvement; backtest events; days where we did worse.

Usage (from backend/):  .venv/Scripts/python -m pipeline.validate [--radius-km 150]
Writes data/demo/validation.json, data/demo/validation_series.json and data/demo/stations.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline import openmeteo
from pipeline.common import Timer, config
from pipeline.downscale import Engine
from pipeline.ingest import Feed
from pipeline.stations import observations
from pipeline.train import categorical

TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
TO_LL = Transformer.from_crs("EPSG:32644", "EPSG:4326", always_xy=True)
SEASONS = [("2024-06-01", "2024-09-30"), ("2025-06-01", "2025-08-24")]  # GSOD currently ends 2025-08-24
PERIOD = "Jun-Sep 2024 + Jun-Aug 2025"
THRESHOLDS = (2.5, 10.0, 64.5)
GAJWEL = (17.85, 78.66)


def box(lat: float, lon: float, half_km: float, step_km: float) -> tuple[np.ndarray, np.ndarray]:
    x0, y0 = TO_UTM.transform(lon, lat)
    offs = np.arange(-half_km, half_km + 1e-9, step_km) * 1000
    X, Y = np.meshgrid(x0 + offs, y0 + offs)
    lo, la = TO_LL.transform(X.ravel(), Y.ravel())
    return np.asarray(la), np.asarray(lo)


def station_forecasts(eng: Engine, st: pd.Series) -> pd.DataFrame:
    """Daily baseline (block value) and Kshetra (downscaled) at one station."""
    plat, plon = box(st["lat"], st["lon"], 10, 10)            # 3 x 3 forecast points, 10 km apart
    clat, clon = box(st["lat"], st["lon"], 13.5, 3)           # 10 x 10 cells, 3 km apart
    cells = pd.DataFrame({"lat": np.append(clat, st["lat"]), "lon": np.append(clon, st["lon"])})
    cells["elev"] = openmeteo.elevation(cells["lat"].tolist(), cells["lon"].tolist())
    block_elev = float(cells["elev"].iloc[:-1].mean())
    out = []
    for start, end in SEASONS:
        res = openmeteo.multi("historical_forecast", plat.tolist(), plon.tolist(), {
            "start_date": start, "end_date": end, "timezone": "GMT", "models": "best_match",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum"}, raw_grid=True)
        arr = lambda k: np.array([[np.nan if v is None else v for v in r["daily"][k]] for r in res], dtype=float)  # noqa: E731
        member = {"tmax": arr("temperature_2m_max"), "tmin": arr("temperature_2m_min"), "rain": arr("precipitation_sum")}
        dates = res[0]["daily"]["time"]
        feed = Feed(dates=dates, lats=plat, lons=plon, members={"best_match": member}, stale=False,
                    source="historical_forecast", official="best_match")
        for d, iso in enumerate(dates):
            blk = {v: float(np.nanmean(member[v][:, d])) for v in member}
            if not all(np.isfinite(list(blk.values()))):
                continue
            c = eng.cells_member(cells, feed, "best_match", d, pd.Timestamp(iso).dayofyear, block_elev)
            boxmean = {v: float(np.mean(c[v][:-1])) for v in ("tmax", "tmin", "rain")}
            rain_st = (c["rain"][-1] * blk["rain"] / boxmean["rain"] if boxmean["rain"] > 0.01
                       else (blk["rain"] if blk["rain"] > 0 else 0.0))
            out.append({
                "station_id": st["station_id"], "date": iso,
                "block_tmax": blk["tmax"], "block_tmin": blk["tmin"], "block_rain": max(blk["rain"], 0.0),
                "ours_tmax": c["tmax"][-1] + blk["tmax"] - boxmean["tmax"],
                "ours_tmin": c["tmin"][-1] + blk["tmin"] - boxmean["tmin"],
                "ours_rain": max(rain_st, 0.0), "ours_p10": float(c["p_heavy"][-1]),
            })
    return pd.DataFrame(out)


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def boot_ci(df: pd.DataFrame, fn, n: int = 1000) -> list[float]:
    rng = np.random.default_rng(0)
    vals = [fn(df.iloc[rng.integers(0, len(df), len(df))]) for _ in range(n)]
    vals = [v for v in vals if v is not None and np.isfinite(v)]
    return [round(float(np.percentile(vals, 5)), 1), round(float(np.percentile(vals, 95)), 1)] if vals else [None, None]


def pct(base, ours):
    return None if not base else round((ours - base) / abs(base) * 100, 1)


def compute(df: pd.DataFrame, stations: pd.DataFrame) -> dict:
    metrics, improvements = [], {}
    n_st = lambda d: int(d["station_id"].nunique())  # noqa: E731
    for v in ("tmax", "tmin"):
        d = df.dropna(subset=[f"obs_{v}", f"block_{v}", f"ours_{v}"])
        for method, col in (("block_baseline", f"block_{v}"), ("panchayatcast", f"ours_{v}")):
            err = d[col] - d[f"obs_{v}"]
            metrics.append({"variable": v, "period": PERIOD, "method": method, "threshold_mm": None,
                            "rmse": round(rmse(d[col], d[f"obs_{v}"]), 2), "bias": round(float(err.mean()), 2),
                            "mae": round(float(err.abs().mean()), 2), "pod": None, "far": None, "csi": None,
                            "n_stations": n_st(d), "n_samples": len(d), "is_placeholder": False})
        f = lambda s, v=v: pct(rmse(s[f"block_{v}"], s[f"obs_{v}"]), rmse(s[f"ours_{v}"], s[f"obs_{v}"]))  # noqa: E731
        improvements[v] = {"metric": "rmse", "change_pct": f(d), "ci90": boot_ci(d, f)}

    r = df.dropna(subset=["obs_rain", "block_rain", "ours_rain"])
    for thr in THRESHOLDS:
        obs = r["obs_rain"].to_numpy() >= thr
        if obs.sum() < 5:
            continue
        for method, col in (("block_baseline", "block_rain"), ("panchayatcast", "ours_rain")):
            s = categorical(obs, r[col].to_numpy() >= thr)
            err = r[col] - r["obs_rain"]
            metrics.append({"variable": "rain", "period": PERIOD, "method": method, "threshold_mm": thr,
                            "rmse": round(rmse(r[col], r["obs_rain"]), 2), "bias": round(float(err.mean()), 2),
                            "mae": round(float(err.abs().mean()), 2), "pod": s["pod"], "far": s["far"], "csi": s["csi"],
                            "n_stations": n_st(r), "n_samples": len(r), "n_events": int(obs.sum()),
                            "is_placeholder": False})

        def csi_change(s, thr=thr):
            o = s["obs_rain"].to_numpy() >= thr
            b = categorical(o, s["block_rain"].to_numpy() >= thr)["csi"]
            u = categorical(o, s["ours_rain"].to_numpy() >= thr)["csi"]
            return None if not b or u is None else (u - b) / b * 100

        improvements[f"rain_csi_{thr:g}"] = {"metric": "csi", "change_pct": round(csi_change(r), 1) if csi_change(r) is not None else None,
                                             "ci90": boot_ci(r, csi_change)}

    # Backtest events and honest counts
    wet = r[r["obs_rain"] >= 10].copy()
    wet["gain"] = (wet["block_rain"] - wet["obs_rain"]).abs() - (wet["ours_rain"] - wet["obs_rain"]).abs()
    names = stations.set_index("station_id")["name"].to_dict()
    top = wet[wet["obs_rain"] >= 15].sort_values("gain", ascending=False).head(5)
    events = [{"id": i + 1, "date": row["date"], "station_id": row["station_id"], "station_name": names.get(row["station_id"]),
               "observed_mm": round(row["obs_rain"], 1), "block_mm": round(row["block_rain"], 1),
               "ours_mm": round(row["ours_rain"], 1), "rank": i + 1, "is_placeholder": False,
               "note": "Automatically selected: largest improvement over the block value on a wet day."}
              for i, (_, row) in enumerate(top.iterrows())]
    counts = {"wet_days": int(len(wet)), "better": int((wet["gain"] > 2).sum()),
              "worse": int((wet["gain"] < -2).sum()), "similar": int((wet["gain"].abs() <= 2).sum())}
    return {"metrics": metrics, "improvements": improvements, "backtest_events": events, "wet_day_counts": counts}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--radius-km", type=float, default=150)
    args = ap.parse_args()
    timer = Timer()
    print("Kshetra validation against ground stations (never used in training)")
    with timer.step("station observations (GSOD / state AWS) + QC"):
        obs = observations(*GAJWEL, args.radius_km, years=[2024, 2025], months=[6, 7, 8, 9])
    stations = (obs.groupby("station_id")
                .agg(name=("name", "first"), lat=("lat", "first"), lon=("lon", "first"), elev=("elev", "first"),
                     distance_km=("distance_km", "first"), source=("source", "first"))
                .reset_index())
    print(f"    {len(stations)} stations: " + ", ".join(f"{n} ({d} km)" for n, d in zip(stations['name'], stations['distance_km'])))
    eng = Engine()
    frames = []
    with timer.step("archived forecasts + downscaling at each station"):
        for _, st in stations.iterrows():
            frames.append(station_forecasts(eng, st))
    fc = pd.concat(frames, ignore_index=True)
    df = fc.merge(obs.rename(columns={"tmax": "obs_tmax", "tmin": "obs_tmin", "rain_mm": "obs_rain"})
                  [["station_id", "date", "obs_tmax", "obs_tmin", "obs_rain", "qc_flag"]], on=["station_id", "date"])
    with timer.step("scores + bootstrap confidence intervals"):
        res = compute(df, stations)

    # Per-station scores (map markers) and daily series (station click)
    per_station, series = [], {}
    for _, st in stations.iterrows():
        d = df[df["station_id"] == st["station_id"]].sort_values("date")
        t = d.dropna(subset=["obs_tmax"])
        rr = d.dropna(subset=["obs_rain"])
        per_station.append({
            "id": st["station_id"], "code": st["station_id"], "name": st["name"], "lat": st["lat"], "lon": st["lon"],
            "elevation_m": st["elev"], "distance_km": st["distance_km"], "source": st["source"],
            "used_in_training": False, "n_days": int(len(d)),
            "tmax_rmse_block": round(rmse(t["block_tmax"], t["obs_tmax"]), 2) if len(t) else None,
            "tmax_rmse_ours": round(rmse(t["ours_tmax"], t["obs_tmax"]), 2) if len(t) else None,
            "rain_mae_block": round(float((rr["block_rain"] - rr["obs_rain"]).abs().mean()), 2) if len(rr) else None,
            "rain_mae_ours": round(float((rr["ours_rain"] - rr["obs_rain"]).abs().mean()), 2) if len(rr) else None,
        })
        rnd = lambda s: [None if pd.isna(x) else round(float(x), 1) for x in s]  # noqa: E731
        series[st["station_id"]] = {"dates": d["date"].tolist(),
                                    **{f"{k}_{v}": rnd(d[f"{k}_{v}"]) for k in ("obs", "block", "ours")
                                       for v in ("tmax", "tmin", "rain")}}
    t = df.dropna(subset=["obs_tmax", "block_tmax", "ours_tmax"])
    summary = {
        "period": PERIOD, "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method_note": ("Stations not used in training. Baseline = the block value (mean of a ~30 km block of real archived "
                        "forecasts) copied to the station. Kshetra = the same forecast downscaled to the station. "
                        "Rain scores follow IMD categorical verification (POD / FAR / CSI)."),
        "caveats": ["Stations are 50-130 km outside Gajwel: this validates the method, not Gajwel's panchayat numbers.",
                    "Archived forecasts are day-1 (Open-Meteo Historical Forecast API), not a full 5-day lead.",
                    "GSOD daily values are UTC days; forecasts use UTC days to match.",
                    "IMD gridded rainfall cells (0.25°, ~25 km) are area means from IMD rain gauges, day ending 08:30 IST: "
                    "a fair check of the block value, a strict one for a point forecast.",
                    "Few stations and one-and-a-half monsoons: see the 90% confidence intervals."],
        "improvements": res["improvements"], "wet_day_counts": res["wet_day_counts"],
        "scatter_tmax": {"obs": t["obs_tmax"].round(1).tolist(), "block": t["block_tmax"].round(1).tolist(),
                         "ours": t["ours_tmax"].round(1).tolist()},
    }
    demo = config()["paths"]["demo"]
    (demo / "validation.json").write_text(json.dumps({"metrics": res["metrics"], "backtest_events": res["backtest_events"],
                                                      "summary": summary}, indent=1), encoding="utf-8")
    (demo / "validation_series.json").write_text(json.dumps(series), encoding="utf-8")
    obs_rows = obs.assign(id=range(1, len(obs) + 1))[["id", "station_id", "date", "rain_mm", "tmax", "tmin", "qc_flag"]]
    (demo / "stations.json").write_text(json.dumps({"stations": per_station,
                                                    "observations": json.loads(obs_rows.round(1).to_json(orient="records"))},
                                                   indent=1), encoding="utf-8")

    print(f"\nScores ({PERIOD}; {len(stations)} stations; baseline = copy the block value):")
    print(f"    {'':<22}{'baseline':>10}{'Kshetra':>15}{'change':>10}   90% CI")
    for v in ("tmax", "tmin"):
        b = next(m for m in res["metrics"] if m["variable"] == v and m["method"] == "block_baseline")
        o = next(m for m in res["metrics"] if m["variable"] == v and m["method"] == "panchayatcast")
        imp = res["improvements"][v]
        print(f"    {v + ' RMSE (°C)':<22}{b['rmse']:>10}{o['rmse']:>15}{imp['change_pct']:>9}%   {imp['ci90']}  (n={o['n_samples']})")
    for thr in THRESHOLDS:
        b = next((m for m in res["metrics"] if m["variable"] == "rain" and m["threshold_mm"] == thr and m["method"] == "block_baseline"), None)
        o = next((m for m in res["metrics"] if m["variable"] == "rain" and m["threshold_mm"] == thr and m["method"] == "panchayatcast"), None)
        if b and o:
            imp = res["improvements"][f"rain_csi_{thr:g}"]
            print(f"    rain >={thr:g} mm POD/FAR/CSI  {b['pod']}/{b['far']}/{b['csi']}  ->  {o['pod']}/{o['far']}/{o['csi']}"
                  f"   CSI change {imp['change_pct']}%  CI {imp['ci90']}  (events={o['n_events']})")
        else:
            print(f"    rain >={thr:g} mm: fewer than 5 observed events - not scored")
    c = res["wet_day_counts"]
    print(f"    wet days (>=10 mm observed): {c['wet_days']}; closer than block {c['better']}, worse {c['worse']}, similar {c['similar']}")
    if res["backtest_events"]:
        e = res["backtest_events"][0]
        print(f"    backtest: {e['date']} {e['station_name']}: observed {e['observed_mm']} mm, block {e['block_mm']} mm, "
              f"Kshetra {e['ours_mm']} mm")
    print("\nTimings:\n" + timer.report())
    print("Wrote data/demo/validation.json, validation_series.json, stations.json")


if __name__ == "__main__":
    main()
