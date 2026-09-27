"""Forecast ingestion adapters. Both produce the same "IMD agromet bulletin" schema.

ingest_openmeteo()  : live (or archived) model forecasts from Open-Meteo, averaged over points inside
                      the block = the block value used in the demo ("Open-Meteo, IMD-format demo feed").
ingest_imd()        : production adapter for IMD's block-level forecast (API access is by IP whitelisting;
                      not available in the prototype). Same output schema, so switching is one config change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from pipeline import openmeteo
from pipeline.common import config

DAILY = [
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "relative_humidity_2m_max", "relative_humidity_2m_min",
    "wind_speed_10m_max", "wind_speed_10m_mean", "wind_direction_10m_dominant", "cloud_cover_mean",
]
SHORT = {"temperature_2m_max": "tmax", "temperature_2m_min": "tmin", "precipitation_sum": "rain",
         "relative_humidity_2m_max": "rh_max", "relative_humidity_2m_min": "rh_min",
         "wind_speed_10m_max": "wind_max", "wind_speed_10m_mean": "wind_mean",
         "wind_direction_10m_dominant": "wind_dir", "cloud_cover_mean": "cloud"}


@dataclass
class Feed:
    """Model forecasts at points inside the block: members[model][var] -> (npoints, ndays)."""

    dates: list[str]
    lats: np.ndarray
    lons: np.ndarray
    members: dict[str, dict[str, np.ndarray]]
    stale: bool
    source: str
    official: str

    def available(self, model: str, var: str = "tmax") -> bool:
        a = self.members.get(model, {}).get(var)
        return a is not None and np.isfinite(a).mean() > 0.9


def ingest_openmeteo(points: list[tuple[float, float]], start: date | None = None, days: int = 5) -> Feed:
    """start=None: live forecast from today. start=date: archived forecast (Historical Forecast API),
    used for replays of past events."""
    cfg = config()["forecast"]
    models = [cfg["official_model"], *cfg["ensemble_models"]]
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    params = {"daily": ",".join(DAILY), "models": ",".join(models), "timezone": config()["timezone"]}
    if start is None:
        kind = "forecast"
        params["forecast_days"] = days
        max_age = cfg["max_age_hours"]
    else:
        kind = "historical_forecast"
        params["start_date"] = start.isoformat()
        params["end_date"] = (start + timedelta(days=days - 1)).isoformat()
        max_age = None
    res = openmeteo.multi(kind, lats, lons, params, chunk=50, max_age_hours=max_age, raw_grid=True)
    members: dict[str, dict[str, np.ndarray]] = {}
    for m in models:
        members[m] = {}
        for v in DAILY:
            key = f"{v}_{m}" if len(models) > 1 else v
            rows = [r["daily"].get(key) for r in res]
            if any(row is None for row in rows):
                continue
            members[m][SHORT[v]] = np.array([[np.nan if x is None else x for x in row] for row in rows], dtype=float)
    return Feed(dates=res[0]["daily"]["time"], lats=np.array(lats), lons=np.array(lons), members=members,
                stale=res.stale, source="openmeteo-imd-format" if start is None else "replay",
                official=cfg["official_model"])


def ingest_imd(block_lgd_code: str, issue_date: date) -> Feed:
    """IMD block-level agromet forecast (GKMS). Needs IMD API access (IP whitelisting).
    Must return the same Feed schema: dates, block point(s) and an 'imd' member with
    tmax, tmin, rain, rh_max, rh_min, wind_mean, wind_dir, cloud for Days 1-5."""
    raise NotImplementedError("IMD API access is not available in the prototype; use ingest_openmeteo().")


def block_bulletin(feed: Feed) -> list[dict]:
    """IMD agromet bulletin fields per day: the block value = mean over the model points."""
    m = feed.members[feed.official]
    mean = lambda v: np.nanmean(m[v], axis=0) if v in m else None  # noqa: E731
    rain, tmax, tmin = mean("rain"), mean("tmax"), mean("tmin")
    rh_max, rh_min = mean("rh_max"), mean("rh_min")
    wind = mean("wind_mean") if "wind_mean" in m and np.isfinite(mean("wind_mean")).all() else mean("wind_max") * 0.6
    cloud = mean("cloud")
    out = []
    for d, iso in enumerate(feed.dates):
        wd = m.get("wind_dir")
        if wd is not None:
            rad = np.radians(wd[:, d])
            direction = float((np.degrees(np.arctan2(np.nanmean(np.sin(rad)), np.nanmean(np.cos(rad)))) + 360) % 360)
        else:
            direction = None
        out.append({
            "day": d + 1, "date": iso,
            "rain_mm": round(float(max(rain[d], 0.0)), 1), "tmax": round(float(tmax[d]), 1), "tmin": round(float(tmin[d]), 1),
            "rh_max": round(float(rh_max[d]), 0) if rh_max is not None else None,
            "rh_min": round(float(rh_min[d]), 0) if rh_min is not None else None,
            "wind_kmh": round(float(wind[d]), 1), "wind_dir": None if direction is None else round(direction),
            "cloud_okta": int(round(float(cloud[d]) / 12.5)) if cloud is not None and np.isfinite(cloud[d]) else None,
        })
    return out
