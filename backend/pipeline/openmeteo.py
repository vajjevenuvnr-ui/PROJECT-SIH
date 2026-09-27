"""Open-Meteo client with an on-disk cache (free, no API key, non-commercial use).

Every response is cached as JSON. Live forecasts are reused for `max_age_hours`; archives and
elevation are cached forever. If the network fails, the last cached copy is served and marked
stale, so a demo never shows an empty map.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import deque
from typing import Any

import httpx

from pipeline.common import config

URLS = {
    "forecast": "https://api.open-meteo.com/v1/forecast",
    "historical_forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "archive": "https://archive-api.open-meteo.com/v1/archive",
    "elevation": "https://api.open-meteo.com/v1/elevation",
}


# Free tier: ~600 weighted calls/minute, 5,000/hour, 10,000/day. A request counts as
# locations x ceil(days / 14) x ceil(variables / 10) calls. We pace to stay under the minute limit.
BUDGET_PER_MIN = 450
_sent: deque[tuple[float, float]] = deque()  # (time, weight)


def request_weight(params: dict) -> float:
    n_loc = len(str(params.get("latitude", "0")).split(","))
    if "start_date" in params and "end_date" in params:
        from datetime import date

        days = (date.fromisoformat(params["end_date"]) - date.fromisoformat(params["start_date"])).days + 1
    else:
        days = int(params.get("forecast_days", 7)) + int(params.get("past_days", 0))
    n_vars = sum(len(str(params.get(k, "")).split(",")) for k in ("daily", "hourly") if params.get(k)) or 1
    if "elevation" in params and "daily" not in params and "hourly" not in params:
        return max(1.0, n_loc / 10)  # elevation API: light
    return n_loc * math.ceil(days / 14) * math.ceil(n_vars / 10)


def _pace(weight: float) -> None:
    now = time.time()
    while _sent and now - _sent[0][0] > 60:
        _sent.popleft()
    used = sum(w for _, w in _sent)
    if used + weight > BUDGET_PER_MIN and _sent:
        wait = 61 - (now - _sent[0][0])
        print(f"    (rate limit pacing: waiting {wait:.0f} s)", flush=True)
        time.sleep(max(1.0, wait))
        _sent.clear()
    _sent.append((time.time(), weight))


class FetchResult(list):
    """List of per-location responses, with a `stale` flag."""

    stale: bool = False


def _cache_path(kind: str, params: dict):
    key = hashlib.sha1((kind + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:20]
    return config()["paths"]["cache"] / f"{kind}-{key}.json"


def get(kind: str, params: dict, max_age_hours: float | None = None) -> tuple[Any, bool]:
    """GET with cache. Returns (json, stale)."""
    path = _cache_path(kind, params)
    if path.exists():
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if max_age_hours is None or age_h < max_age_hours:
            return json.loads(path.read_text(encoding="utf-8")), False
    last_exc: Exception | None = None
    _pace(request_weight(params))
    for attempt in range(5):
        try:
            r = httpx.get(URLS[kind], params=params, timeout=120)
            if r.status_code == 429:
                print("    (Open-Meteo rate limit hit: waiting 61 s)", flush=True)
                time.sleep(61)
                _sent.clear()
                raise httpx.HTTPStatusError("HTTP 429", request=r.request, response=r)
            if r.status_code >= 500:
                raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
            data = r.json()
            if isinstance(data, dict) and data.get("error"):
                raise ValueError(f"Open-Meteo error: {data.get('reason')}")
            r.raise_for_status()
            path.write_text(json.dumps(data), encoding="utf-8")
            return data, False
        except (httpx.HTTPError, ValueError) as exc:
            last_exc = exc
            if isinstance(exc, ValueError):
                break  # bad request: retrying won't help
            time.sleep(2 * (attempt + 1))
    if path.exists():
        print(f"    ! network failed ({last_exc}); using cached {kind} data (stale)")
        return json.loads(path.read_text(encoding="utf-8")), True
    raise RuntimeError(f"Open-Meteo {kind} request failed and nothing is cached: {last_exc}")


def multi(kind: str, lats: list[float], lons: list[float], params: dict, chunk: int = 50,
          max_age_hours: float | None = None, raw_grid: bool = False) -> FetchResult:
    """Many locations in chunked requests. `raw_grid=True` disables Open-Meteo's own elevation
    downscaling (elevation=nan) so we get the model's grid-cell values."""
    out = FetchResult()
    for i in range(0, len(lats), chunk):
        la, lo = lats[i:i + chunk], lons[i:i + chunk]
        p = {**params, "latitude": ",".join(f"{x:.4f}" for x in la), "longitude": ",".join(f"{x:.4f}" for x in lo)}
        if raw_grid:
            p["elevation"] = ",".join(["nan"] * len(la))
        data, stale = get(kind, p, max_age_hours)
        out.extend(data if isinstance(data, list) else [data])
        out.stale = out.stale or stale
    return out


def elevation(lats: list[float], lons: list[float]) -> list[float]:
    """Copernicus DEM (90 m) elevation in metres for many points."""
    out: list[float] = []
    for i in range(0, len(lats), 100):
        data, _ = get("elevation", {"latitude": ",".join(f"{x:.5f}" for x in lats[i:i + 100]),
                                    "longitude": ",".join(f"{x:.5f}" for x in lons[i:i + 100])})
        out.extend(float(v) for v in data["elevation"])
    return out
