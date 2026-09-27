"""Train the hybrid downscaling models (perfect prognosis).

Coarse input : ERA5 0.25° (~28 km)         via Open-Meteo archive (raw grid values, no Open-Meteo downscaling)
Fine target  : ERA5-Land 0.1° (~9 km) for temperature, ECMWF IFS (~9 km) for rain
               (Open-Meteo does not serve ERA5-Land precipitation; CHIRPS 0.05° is the planned upgrade)
Terrain      : Copernicus DEM 90 m          cell-mean elevation of every coarse / fine grid cell

Temperature  : T_phys = T_coarse + lapse * dz_km ;  XGBoost learns the residual
Rain         : P(rain >= 2.5 mm), P(rain >= 10 mm) classifiers + amount regressor on wet days
               + quantile mapping of predicted amounts to the observed fine-scale distribution

Skill is measured on fine cells held out of training, against the "copy the coarse value" baseline.
This is model-to-model (perfect-prognosis) skill; validation against AWS stations is Phase 8.

Usage (from backend/):  .venv/Scripts/python -m pipeline.train
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

from pipeline import openmeteo
from pipeline.common import Timer, config
from pipeline.grid import load_block

VARS = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"]
SHORT = {"temperature_2m_max": "tmax", "temperature_2m_min": "tmin", "precipitation_sum": "rain"}
FEATURES_T = ["coarse", "dz_km", "elev_km", "lat", "lon", "doy_sin", "doy_cos"]
FEATURES_R = ["coarse", "dz_km", "elev_km", "lat", "lon", "doy_sin", "doy_cos", "clim_ratio"]
WET, HEAVY = 2.5, 10.0
QUANTILES = np.linspace(0.0, 1.0, 101)


# ---------------------------------------------------------------- data
def grid_points(lo: float, hi: float, res: float) -> np.ndarray:
    return np.round(np.arange(np.ceil(lo / res) * res, hi + 1e-9, res), 4)


def cell_mean_elevation(lats: np.ndarray, lons: np.ndarray, res: float, n: int) -> np.ndarray:
    """Mean DEM elevation of each (lat, lon) grid cell, from n x n samples."""
    offs = (np.arange(n) + 0.5) / n - 0.5
    sl, so = [], []
    for la, lo in zip(lats, lons):
        for dy in offs:
            for dx in offs:
                sl.append(la + dy * res)
                so.append(lo + dx * res)
    z = np.array(openmeteo.elevation(sl, so)).reshape(len(lats), n * n)
    return z.mean(axis=1)


def fetch_daily(lats, lons, model: str, start: str, end: str, variables: list[str] = VARS) -> dict[str, np.ndarray]:
    res = openmeteo.multi("archive", list(lats), list(lons), {
        "start_date": start, "end_date": end, "daily": ",".join(variables), "models": model,
        "timezone": config()["timezone"],
    }, chunk=25, raw_grid=True)
    out = {SHORT[v]: np.array([[np.nan if x is None else x for x in r["daily"][v]] for r in res], dtype=float)
           for v in variables}
    out["time"] = np.array(res[0]["daily"]["time"])
    return out


def bilinear_weights(glat: np.ndarray, glon: np.ndarray, lat: np.ndarray, lon: np.ndarray):
    """Indices and weights to interpolate a (lat, lon) grid to points."""
    i = np.clip(np.searchsorted(glat, lat) - 1, 0, len(glat) - 2)
    j = np.clip(np.searchsorted(glon, lon) - 1, 0, len(glon) - 2)
    ty = (lat - glat[i]) / (glat[i + 1] - glat[i])
    tx = (lon - glon[j]) / (glon[j + 1] - glon[j])
    return i, j, ty, tx


def interp(field: np.ndarray, w) -> np.ndarray:
    """field: (nlat, nlon, ...) -> (npoints, ...)."""
    i, j, ty, tx = w
    ty = ty.reshape(-1, *([1] * (field.ndim - 2)))
    tx = tx.reshape(-1, *([1] * (field.ndim - 2)))
    return ((1 - ty) * (1 - tx) * field[i, j] + (1 - ty) * tx * field[i, j + 1]
            + ty * (1 - tx) * field[i + 1, j] + ty * tx * field[i + 1, j + 1])


def build_table(timer: Timer) -> tuple[pd.DataFrame, dict]:
    cfg = config()
    tc = cfg["training"]
    block, _ = load_block(cfg["block_id"])
    minx, miny, maxx, maxy = block["shape"].bounds
    m = tc["margin_deg"]
    flat, flon = grid_points(miny - m, maxy + m, 0.1), grid_points(minx - m, maxx + m, 0.1)
    clat = grid_points(flat.min() - 0.25, flat.max() + 0.25, 0.25)
    clon = grid_points(flon.min() - 0.25, flon.max() + 0.25, 0.25)
    FL, FO = np.meshgrid(flat, flon, indexing="ij")
    fine_lat, fine_lon = FL.ravel(), FO.ravel()
    CL, CO = np.meshgrid(clat, clon, indexing="ij")
    print(f"    {len(fine_lat)} fine ERA5-Land cells, {CL.size} coarse ERA5 cells")

    with timer.step("terrain: cell-mean elevations"):
        fine_elev = cell_mean_elevation(fine_lat, fine_lon, 0.1, 4)
        coarse_elev = cell_mean_elevation(CL.ravel(), CO.ravel(), 0.25, 5).reshape(CL.shape)

    frames = []
    with timer.step("download ERA5 + ERA5-Land (monsoon seasons, cached)"):
        for y in tc["years"]:
            s, e = f"{y}-{tc['season'][0]}", f"{y}-{tc['season'][1]}"
            fine = fetch_daily(fine_lat, fine_lon, tc["fine_model"], s, e, VARS[:2])
            fine["rain"] = fetch_daily(fine_lat, fine_lon, tc["fine_rain_model"], s, e, VARS[2:])["rain"]
            coarse = fetch_daily(CL.ravel(), CO.ravel(), tc["coarse_model"], s, e)
            frames.append((fine, coarse))

    w = bilinear_weights(clat, clon, fine_lat, fine_lon)
    c_elev_at_fine = interp(coarse_elev[..., None], w)[:, 0]
    rows = []
    for fine, coarse in frames:
        days = pd.to_datetime(fine["time"])
        doy = days.dayofyear.to_numpy()
        for var in ("tmax", "tmin", "rain"):
            cfield = coarse[var].reshape(len(clat), len(clon), -1)
            coarse[var + "_at_fine"] = interp(cfield, w)  # (nfine, ndays)
        for p in range(len(fine_lat)):
            rows.append(pd.DataFrame({
                "point": p, "date": days, "lat": fine_lat[p], "lon": fine_lon[p],
                "elev_km": fine_elev[p] / 1000, "dz_km": (c_elev_at_fine[p] - fine_elev[p]) / 1000,
                "doy_sin": np.sin(2 * np.pi * doy / 365.25), "doy_cos": np.cos(2 * np.pi * doy / 365.25),
                **{f"c_{v}": coarse[v + "_at_fine"][p] for v in ("tmax", "tmin", "rain")},
                **{f"f_{v}": fine[v][p] for v in ("tmax", "tmin", "rain")},
            }))
    df = pd.concat(rows, ignore_index=True).dropna()
    info = {"fine_points": len(fine_lat), "coarse_points": int(CL.size), "days": int(df["date"].nunique()),
            "rows": len(df), "years": tc["years"], "season": tc["season"]}
    return df, info


# ---------------------------------------------------------------- models
def _xgb_reg():
    return XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.9,
                        n_jobs=4, random_state=0)


def _xgb_clf():
    return XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.9,
                         n_jobs=4, random_state=0, eval_metric="logloss")


def clim_ratios(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("point").agg(lat=("lat", "first"), lon=("lon", "first"), f=("f_rain", "mean"), c=("c_rain", "mean"))
    g["ratio"] = (g["f"] + 0.1) / (g["c"] + 0.1)
    return g[["lat", "lon", "ratio"]].reset_index()


def idw(src_lat, src_lon, src_val, lat, lon, power: float = 2.0) -> np.ndarray:
    d2 = (np.subtract.outer(lat, src_lat) ** 2 + np.subtract.outer(lon, src_lon) ** 2) + 1e-10
    w = 1 / d2 ** (power / 2)
    return (w * src_val).sum(axis=1) / w.sum(axis=1)


def fit(df: pd.DataFrame, lapse: float) -> dict:
    """Fit all models on df (training cells). Returns model objects + QM arrays."""
    cr = clim_ratios(df)
    df = df.assign(clim_ratio=df["point"].map(dict(zip(cr["point"], cr["ratio"]))))
    m = {}
    for v in ("tmax", "tmin"):
        X = df.assign(coarse=df[f"c_{v}"])[FEATURES_T]
        y = df[f"f_{v}"] - (df[f"c_{v}"] + lapse * df["dz_km"])
        m[v] = _xgb_reg().fit(X, y)
    Xr = df.assign(coarse=df["c_rain"])[FEATURES_R]
    m["wet"] = _xgb_clf().fit(Xr, (df["f_rain"] >= WET).astype(int))
    m["heavy"] = _xgb_clf().fit(Xr, (df["f_rain"] >= HEAVY).astype(int))
    wet = df["f_rain"] >= WET
    m["amount"] = _xgb_reg().fit(Xr[wet], np.log1p(df.loc[wet, "f_rain"]))
    pred = np.expm1(m["amount"].predict(Xr[wet]))
    m["qm_pred"] = np.quantile(pred, QUANTILES).tolist()
    m["qm_obs"] = np.quantile(df.loc[wet, "f_rain"], QUANTILES).tolist()
    return m


def quantile_map(x: np.ndarray, qm_pred, qm_obs) -> np.ndarray:
    return np.interp(x, qm_pred, qm_obs)


def predict_rain(m: dict, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Expected rain (mm), P(>=2.5 mm), P(>=10 mm)."""
    p_wet = m["wet"].predict_proba(X)[:, 1]
    p_heavy = m["heavy"].predict_proba(X)[:, 1]
    amount = quantile_map(np.expm1(m["amount"].predict(X)), m["qm_pred"], m["qm_obs"])
    return p_wet * amount, p_wet, p_heavy


def categorical(obs: np.ndarray, fc: np.ndarray) -> dict:
    hit = int(np.sum(fc & obs))
    miss = int(np.sum(~fc & obs))
    fa = int(np.sum(fc & ~obs))
    pod = hit / (hit + miss) if hit + miss else None
    far = fa / (hit + fa) if hit + fa else None
    csi = hit / (hit + miss + fa) if hit + miss + fa else None
    r = lambda v: None if v is None else round(v, 3)  # noqa: E731
    return {"pod": r(pod), "far": r(far), "csi": r(csi), "hits": hit, "misses": miss, "false_alarms": fa}


def evaluate(df: pd.DataFrame, lapse: float, holdout_fraction: float) -> dict:
    """Train on most fine cells, score on held-out cells vs the copy-coarse baseline."""
    rng = np.random.default_rng(0)
    points = df["point"].unique()
    test_pts = rng.choice(points, size=max(2, int(len(points) * holdout_fraction)), replace=False)
    train, test = df[~df["point"].isin(test_pts)], df[df["point"].isin(test_pts)].copy()
    m = fit(train, lapse)
    cr = clim_ratios(train)
    test["clim_ratio"] = idw(cr["lat"].to_numpy(), cr["lon"].to_numpy(), cr["ratio"].to_numpy(),
                             test["lat"].to_numpy(), test["lon"].to_numpy())
    rmse = lambda a, b: round(float(np.sqrt(np.mean((a - b) ** 2))), 3)  # noqa: E731
    out = {"holdout_cells": int(len(test_pts)), "holdout_rows": len(test)}
    for v in ("tmax", "tmin"):
        phys = test[f"c_{v}"] + lapse * test["dz_km"]
        ml = phys + m[v].predict(test.assign(coarse=test[f"c_{v}"])[FEATURES_T])
        out[v] = {"rmse_baseline": rmse(test[f"c_{v}"], test[f"f_{v}"]), "rmse_lapse": rmse(phys, test[f"f_{v}"]),
                  "rmse_model": rmse(ml, test[f"f_{v}"])}
    rain, _, p_heavy = predict_rain(m, test.assign(coarse=test["c_rain"])[FEATURES_R])
    obs = test["f_rain"].to_numpy()
    out["rain"] = {
        "rmse_baseline": rmse(test["c_rain"], obs), "rmse_model": rmse(rain, obs),
        "heavy10_baseline": categorical(obs >= HEAVY, test["c_rain"].to_numpy() >= HEAVY),
        "heavy10_model": categorical(obs >= HEAVY, p_heavy >= 0.5),
    }
    return out


def false_onset(df: pd.DataFrame) -> dict:
    """For each 'sowing rain' (>=20 mm over 2 days) at a fine cell: was it followed by a >=10-day dry
    spell (<2.5 mm/day) within 30 days? Probability by month = false-onset risk."""
    out: dict[int, list[int]] = {}
    for _, g in df.sort_values("date").groupby("point"):
        r = g.set_index("date")["f_rain"]
        two = r.rolling(2).sum()
        for d in two[two >= 20].index:
            nxt = r[(r.index > d) & (r.index <= d + pd.Timedelta(days=30))]
            if len(nxt) < 25:
                continue
            dry = (nxt < 2.5).astype(int)
            longest = int(dry.groupby((dry != dry.shift()).cumsum()).sum().max())
            out.setdefault(d.month, []).append(int(longest >= 10))
    return {str(m): {"events": len(v), "p": round(float(np.mean(v)), 2)} for m, v in sorted(out.items())}


def save(m: dict, meta: dict) -> None:
    d = config()["paths"]["models"]
    for k in ("tmax", "tmin", "amount"):
        m[k].save_model(d / f"{k}.json")
    for k in ("wet", "heavy"):
        m[k].save_model(d / f"{k}.json")
    (d / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def main() -> None:
    cfg = config()
    lapse = cfg["lapse_rate_c_per_km"]
    timer = Timer()
    print("Kshetra - training the hybrid downscaling models")
    df, info = build_table(timer)
    print(f"    training table: {info['rows']:,} rows ({info['fine_points']} cells x {info['days']} days)")
    with timer.step("hold-out evaluation (20% of cells)"):
        skill = evaluate(df, lapse, cfg["training"]["holdout_fraction"])
    with timer.step("final fit on all cells"):
        m = fit(df, lapse)
        cr = clim_ratios(df)
    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": ("perfect prognosis: ERA5 0.25° -> ERA5-Land 0.1° (temperature) / ECMWF IFS 9 km (rain), "
                   "Open-Meteo archive; lapse-rate + XGBoost; rain two-stage + quantile mapping"),
        "lapse_rate_c_per_km": lapse, "features_t": FEATURES_T, "features_r": FEATURES_R,
        "thresholds_mm": {"wet": WET, "heavy": HEAVY}, "qm_pred": m["qm_pred"], "qm_obs": m["qm_obs"],
        "clim_ratio": cr[["lat", "lon", "ratio"]].round(4).to_dict(orient="list"),
        "training": info, "skill_holdout": skill, "false_onset": false_onset(df),
    }
    save(m, meta)
    print("\nHold-out skill (fine cells never used in training; baseline = copy the coarse value):")
    for v in ("tmax", "tmin"):
        s = skill[v]
        print(f"    {v}: RMSE baseline {s['rmse_baseline']} -> lapse {s['rmse_lapse']} -> lapse+XGBoost {s['rmse_model']} °C")
    r = skill["rain"]
    print(f"    rain RMSE: baseline {r['rmse_baseline']} -> model {r['rmse_model']} mm")
    b, mm = r["heavy10_baseline"], r["heavy10_model"]
    print(f"    rain >=10 mm  POD/FAR/CSI: baseline {b['pod']}/{b['far']}/{b['csi']}  ->  model {mm['pod']}/{mm['far']}/{mm['csi']}")
    print("    false-onset risk by month (dry spell after sowing rains):",
          {m: v["p"] for m, v in meta["false_onset"].items()})
    print("\nTimings:\n" + timer.report())
    print(f"Models saved to {config()['paths']['models'].relative_to(config()['paths']['models'].parents[1])}")


if __name__ == "__main__":
    main()
