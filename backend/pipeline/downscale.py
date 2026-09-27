"""Inference: block forecast -> 1 km cells -> panchayat values, with mass consistency and confidence.

For each forecast day and each model member:
  1. interpolate the member's point forecasts to the 1 km cells (IDW)
  2. temperature: T = T_coarse + lapse * dz_km + XGBoost residual       (dz = block mean elev - cell elev)
     rain       : P(>=2.5), P(>=10) and amount (quantile-mapped), expected = P(wet) x amount
  3. average cells per panchayat
  4. MASS CONSISTENCY: rescale so the panchayat mean equals that member's block value
     (additive for temperature, multiplicative for rain / wind)
RH follows from temperature (constant vapour pressure); wind uses terrain exposure (TPI).
Confidence comes from the spread between members (ECMWF / GFS / ICON) plus lead time.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

from pipeline.common import config
from pipeline.ingest import Feed
from pipeline.train import FEATURES_R, FEATURES_T, idw, predict_rain


def additive(values: np.ndarray, target: float) -> np.ndarray:
    return values + (target - values.mean())


def multiplicative(values: np.ndarray, target: float) -> np.ndarray:
    if target <= 0:
        return np.zeros_like(values)
    if values.sum() <= 0:
        return np.full_like(values, target, dtype=float)
    return values * (target / values.mean())


def round_keep_mean(values: np.ndarray, target: float, decimals: int = 1, floor: float | None = None) -> np.ndarray:
    """Round, then nudge one value so the rounded mean still equals the (rounded) target."""
    v = np.round(values, decimals)
    residual = round(round(target, decimals) * len(v) - v.sum(), decimals)
    if residual:
        order = np.argsort(-v)
        for i in order:
            if floor is None or v[i] + residual >= floor:
                v[i] = round(v[i] + residual, decimals)
                break
    return v


def es(t_c: np.ndarray) -> np.ndarray:
    """Saturation vapour pressure (hPa), Magnus formula."""
    return 6.112 * np.exp(17.62 * t_c / (243.12 + t_c))


class Engine:
    def __init__(self):
        d = config()["paths"]["models"]
        if not (d / "meta.json").exists():
            raise FileNotFoundError("No trained models. Run: .venv/Scripts/python -m pipeline.train")
        self.meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        self.m = {}
        for k in ("tmax", "tmin", "amount"):
            self.m[k] = XGBRegressor()
            self.m[k].load_model(d / f"{k}.json")
        for k in ("wet", "heavy"):
            self.m[k] = XGBClassifier()
            self.m[k].load_model(d / f"{k}.json")
        self.m["qm_pred"], self.m["qm_obs"] = self.meta["qm_pred"], self.meta["qm_obs"]
        self.lapse = self.meta["lapse_rate_c_per_km"]

    def cells_member(self, cells: pd.DataFrame, feed: Feed, model: str, d: int, doy: int, block_elev: float) -> dict:
        m = feed.members[model]
        lat, lon = cells["lat"].to_numpy(), cells["lon"].to_numpy()

        def at_cells(var):
            vals = m[var][:, d]
            ok = np.isfinite(vals)
            return idw(feed.lats[ok], feed.lons[ok], vals[ok], lat, lon)

        base = pd.DataFrame({
            "dz_km": (block_elev - cells["elev"].to_numpy()) / 1000, "elev_km": cells["elev"].to_numpy() / 1000,
            "lat": lat, "lon": lon,
            "doy_sin": np.sin(2 * np.pi * doy / 365.25), "doy_cos": np.cos(2 * np.pi * doy / 365.25),
        })
        out = {}
        for v in ("tmax", "tmin"):
            coarse = at_cells(v)
            X = base.assign(coarse=coarse)[FEATURES_T]
            out[v] = coarse + self.lapse * base["dz_km"].to_numpy() + self.m[v].predict(X)
        cr = self.meta["clim_ratio"]
        Xr = base.assign(coarse=np.maximum(at_cells("rain"), 0),
                         clim_ratio=idw(np.array(cr["lat"]), np.array(cr["lon"]), np.array(cr["ratio"]), lat, lon))[FEATURES_R]
        out["rain"], out["p_wet"], out["p_heavy"] = predict_rain(self.m, Xr)
        return out


def downscale(feed: Feed, bulletin: list[dict], cells: pd.DataFrame, run_id: int) -> list[dict]:
    """Panchayat forecast rows (same schema as the database / demo JSON)."""
    eng = Engine()
    block_elev = float(cells["elev"].mean())
    gp_ids = np.array(sorted(cells["gp_id"].unique()))
    tpi = cells.groupby("gp_id")["tpi"].mean().reindex(gp_ids).to_numpy()
    members = [m for m in [feed.official, *config()["forecast"]["ensemble_models"]] if feed.available(m)]
    rows = []
    for d, b in enumerate(bulletin):
        doy = pd.Timestamp(b["date"]).dayofyear
        per = {}
        for model in members:
            c = eng.cells_member(cells, feed, model, d, doy, block_elev)
            g = pd.DataFrame({"gp_id": cells["gp_id"], **c}).groupby("gp_id").mean().reindex(gp_ids)
            mm = feed.members[model]
            blk = {v: float(np.nanmean(mm[v][:, d])) for v in ("tmax", "tmin", "rain")}
            per[model] = {
                "tmax": additive(g["tmax"].to_numpy(), blk["tmax"]),
                "tmin": additive(g["tmin"].to_numpy(), blk["tmin"]),
                "rain": multiplicative(np.maximum(g["rain"].to_numpy(), 0), max(blk["rain"], 0)),
                "p_wet": g["p_wet"].to_numpy(), "p_heavy": g["p_heavy"].to_numpy(),
            }
        off = per[feed.official]
        # Official values: consistent with the bulletin (the "IMD block value").
        tmax = round_keep_mean(additive(off["tmax"], b["tmax"]), b["tmax"])
        tmin = round_keep_mean(additive(off["tmin"], b["tmin"]), b["tmin"])
        tmin = np.minimum(tmin, tmax - 0.5)
        rain = round_keep_mean(multiplicative(off["rain"], b["rain_mm"]), b["rain_mm"], floor=0.0)
        # RH from temperature at constant vapour pressure, then consistent with the block mean RH.
        rh_block = (b["rh_max"] + b["rh_min"]) / 2 if b["rh_max"] is not None else 70.0
        t_mean_block = (b["tmax"] + b["tmin"]) / 2
        rh = np.clip(rh_block * es(np.array(t_mean_block)) / es((tmax + tmin) / 2), 5, 100)
        rh = np.clip(round_keep_mean(additive(rh, rh_block), rh_block), 5, 100)
        wind = round_keep_mean(multiplicative(np.clip(1 + 0.012 * tpi, 0.7, 1.3), b["wind_kmh"]), b["wind_kmh"], floor=0.0)

        # Ensemble spread -> range and confidence.
        stack_rain = np.vstack([per[m]["rain"] for m in members])
        stack_t = np.vstack([per[m]["tmax"] for m in members])
        rain_min = np.minimum(stack_rain.min(axis=0), rain)
        rain_max = np.maximum(stack_rain.max(axis=0), rain)
        spread = (0.65 * np.minimum(stack_rain.std(axis=0) / (stack_rain.mean(axis=0) + 3.0), 1.0)
                  + 0.35 * np.minimum(stack_t.std(axis=0) / 2.5, 1.0) + 0.03 * d)
        if len(members) == 1:
            spread = spread + 0.3  # no ensemble available: be modest
        conf = np.where(spread < 0.3, "high", np.where(spread < 0.55, "medium", "low"))

        for i, gid in enumerate(gp_ids):
            rows.append({
                "run_id": run_id, "panchayat_id": int(gid), "day": d + 1, "date": b["date"],
                "rain_mm": float(rain[i]), "rain_min": round(float(max(rain_min[i], 0)), 1),
                "rain_max": round(float(rain_max[i]), 1),
                "rain_prob_2_5mm": round(float(off["p_wet"][i]), 2), "rain_prob_10mm": round(float(off["p_heavy"][i]), 2),
                "tmax": float(tmax[i]), "tmin": float(round(tmin[i], 1)), "rh": float(round(rh[i], 1)),
                "wind_kmh": float(wind[i]), "confidence": str(conf[i]), "model_spread": round(float(spread[i]), 3),
            })
    for k, r in enumerate(rows, start=1):
        r["id"] = k
    return rows
