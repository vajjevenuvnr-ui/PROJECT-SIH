"""Demo seed for Kshetra: Telangana > Siddipet > Gajwel, 24 gram panchayats.

Outputs (deterministic - same data on every run):
  * backend/data/demo/*.json      -> used by Demo Mode (works offline, no database)
  * backend/supabase/seed.sql     -> paste into the Supabase SQL editor after 0001_schema.sql

Usage (from backend/):
  .venv/Scripts/python -m scripts.seed_demo            # write JSON + seed.sql
  .venv/Scripts/python -m scripts.seed_demo --apply    # also run schema + seed on DATABASE_URL

IMPORTANT - what is real and what is not:
  * District, block and GP boundaries are ILLUSTRATIVE: Voronoi cells around approximate
    locations, not official LGD / Bhuvan geometry. GP names are Gajwel-area village names used
    for the demo; LGD codes are placeholders (prefix "DEMO-"). Replace with the real pilot
    dataset in Phase 7.
  * Forecast values are SYNTHETIC but physically shaped (lapse rate, a coherent rain cell,
    mass consistency with the block value). Phase 7 replaces them with real downscaled output.
  * Validation metrics and the backtest event are PLACEHOLDERS (is_placeholder = true).
    Phase 8 replaces them with real results. The UI must label placeholders as illustrative.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from shapely import wkt as shp_wkt
from shapely.geometry import MultiPoint, MultiPolygon, Point, Polygon, mapping
from shapely.ops import voronoi_diagram

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEMO_DIR = BACKEND_DIR / "data" / "demo"   # served by Demo Mode (the pipeline may overwrite forecast.json)
SEED_DIR = BACKEND_DIR / "data" / "seed"   # fixed copy used by the tests
MIGRATIONS_DIR = BACKEND_DIR / "supabase" / "migrations"
SEED_SQL = BACKEND_DIR / "supabase" / "seed.sql"

RNG_SEED = 26074
LAPSE_C_PER_M = 6.5 / 1000.0
IST = timezone(timedelta(hours=5, minutes=30))

# Monday 20 July 2026, 06:00 IST. Day 2 (Tuesday) is the demo's heavy-rain day.
ISSUED_AT = datetime(2026, 7, 20, 6, 0, tzinfo=IST)
FORECAST_DATES = [ISSUED_AT.date() + timedelta(days=i) for i in range(5)]

# Official-style block forecast for Gajwel (IMD agromet bulletin fields), Days 1-5.
BLOCK_FC = {
    "rain_mm": [3.0, 8.0, 5.0, 0.5, 1.0],
    "tmax": [33.0, 30.0, 31.0, 32.0, 33.0],
    "tmin": [24.0, 23.0, 23.0, 24.0, 24.0],
    "rh_max": [85.0, 92.0, 88.0, 80.0, 78.0],
    "rh_min": [60.0, 72.0, 65.0, 55.0, 52.0],
    "wind_kmh": [10.0, 14.0, 12.0, 8.0, 9.0],
    "wind_dir": [240.0, 250.0, 245.0, 230.0, 235.0],
    "cloud_okta": [5, 7, 6, 3, 3],
}

# Approximate outline of Siddipet district (lon, lat). Illustrative only.
DISTRICT_OUTLINE = [
    (78.48, 17.80), (78.52, 17.66), (78.95, 17.66), (79.05, 17.85), (79.22, 18.05),
    (79.10, 18.25), (78.80, 18.33), (78.55, 18.25), (78.50, 18.00),
]

# Block (mandal) seed points (lon, lat) used to split the district into illustrative block cells.
BLOCK_SEEDS = [
    ("DEMO-B-GAJ", "Gajwel", "గజ్వేల్", "गजवेल", (78.68, 17.84)),
    ("DEMO-B-JAG", "Jagdevpur", "జగదేవ్‌పూర్", "जगदेवपुर", (78.80, 17.99)),
    ("DEMO-B-MUL", "Mulugu", "ములుగు", "मुलुगु", (78.58, 17.72)),
    ("DEMO-B-MAR", "Markook", "మర్కూక్", "मरकूक", (78.82, 17.74)),
    ("DEMO-B-THO", "Thoguta", "తొగుట", "तोगुटा", (78.60, 18.05)),
    ("DEMO-B-DUB", "Dubbak", "దుబ్బాక", "दुब्बाक", (78.68, 18.20)),
    ("DEMO-B-SDP", "Siddipet Urban", "సిద్దిపేట అర్బన్", "सिद्दीपेट शहरी", (78.90, 18.12)),
    ("DEMO-B-HUS", "Husnabad", "హుస్నాబాద్", "हुस्नाबाद", (79.10, 18.08)),
]

# Illustrative Gajwel-area GP names. Telugu spellings need native-speaker review.
GP_NAMES = [
    ("Ahmadipur", "అహ్మదీపూర్"), ("Akaram", "అకారం"), ("Bejgaon", "బేజ్‌గాం"),
    ("Bayyaram", "బయ్యారం"), ("Dharmareddipally", "ధర్మారెడ్డిపల్లి"), ("Koluthur", "కొల్తూర్"),
    ("Kodakandla", "కొడకండ్ల"), ("Mutrajpally", "ముత్రాజ్‌పల్లి"), ("Pregnapur", "ప్రజ్ఞాపూర్"),
    ("Rimmanaguda", "రిమ్మనగూడ"), ("Sangapur", "సంగాపూర్"), ("Singaipally", "సింగాయపల్లి"),
    ("Srigiripally", "శ్రీగిరిపల్లి"), ("Kolgur", "కొల్గూర్"), ("Jaligaon", "జాలిగాం"),
    ("Lingarajpally", "లింగరాజుపల్లి"), ("Mamidyal", "మామిడ్యాల"), ("Pidicherla", "పిడిచెర్ల"),
    ("Rajireddipally", "రాజిరెడ్డిపల్లి"), ("Datharpally", "దాతర్‌పల్లి"), ("Kistampet", "కిష్టంపేట"),
    ("Bangla Venkatapur", "బంగ్లా వెంకటాపూర్"), ("Thigul", "తిగుల్"), ("Gowraram", "గౌరారం"),
]
DEMO_GP = "Ahmadipur"
DEMO_GP_FARMERS = 312


@dataclass
class Dataset:
    states: list[dict] = field(default_factory=list)
    districts: list[dict] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)
    panchayats: list[dict] = field(default_factory=list)
    forecast_runs: list[dict] = field(default_factory=list)
    block_forecasts: list[dict] = field(default_factory=list)
    panchayat_forecasts: list[dict] = field(default_factory=list)
    aws_stations: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    validation_metrics: list[dict] = field(default_factory=list)
    backtest_events: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _km_xy(lon: float, lat: float, lon0: float, lat0: float) -> tuple[float, float]:
    """Approximate local x/y in km relative to (lon0, lat0)."""
    return (lon - lon0) * 111.32 * math.cos(math.radians(lat0)), (lat - lat0) * 110.57


def _as_multi(g) -> MultiPolygon:
    if isinstance(g, MultiPolygon):
        return g
    if isinstance(g, Polygon):
        return MultiPolygon([g])
    polys = [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
    return MultiPolygon(polys)


def _voronoi_cells(points: list[tuple[float, float]], clip: Polygon) -> list[MultiPolygon]:
    """Voronoi cell for each point, clipped to `clip`, in the same order as `points`."""
    env = clip.buffer(0.5).envelope
    cells = list(voronoi_diagram(MultiPoint(points), envelope=env).geoms)
    out = []
    for p in points:
        pt = Point(p)
        cell = next(c for c in cells if c.contains(pt))
        out.append(_as_multi(cell.intersection(clip)))
    return out


def _warp(g):
    """Smooth, continuous displacement so Voronoi edges look like natural boundaries.

    The same function is applied to every geometry, so shared edges stay shared.
    """
    import shapely

    def f(coords: np.ndarray) -> np.ndarray:
        x, y = coords[:, 0], coords[:, 1]
        dx = 0.009 * np.sin(y * 52.0 + 1.3) + 0.003 * np.sin(y * 140.0 + x * 40.0)
        dy = 0.009 * np.sin(x * 52.0 + 0.4) + 0.003 * np.cos(x * 140.0 - y * 35.0)
        return np.column_stack([x + dx, y + dy])

    return shapely.transform(shapely.segmentize(g, 0.003), f)


def _poisson_points(poly: Polygon, n: int, min_km: float, rng: np.random.Generator) -> list[tuple[float, float]]:
    minx, miny, maxx, maxy = poly.bounds
    lat0 = (miny + maxy) / 2
    pts: list[tuple[float, float]] = []
    tries = 0
    while len(pts) < n:
        tries += 1
        if tries > 50000:
            raise RuntimeError("Could not place panchayat points; lower min_km")
        p = (rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if not poly.buffer(-0.01).contains(Point(p)):
            continue
        if all(math.dist(_km_xy(*p, lon0=q[0], lat0=lat0), (0, 0)) >= min_km for q in pts):
            pts.append(p)
    return pts


# ---------------------------------------------------------------------------
# Field helpers (mass consistency)
# ---------------------------------------------------------------------------
def _fix_mean(values: np.ndarray, target: float, decimals: int = 1, protect: set[int] | None = None) -> np.ndarray:
    """Round to `decimals` and nudge one element so the simple mean equals `target` exactly."""
    protect = protect or set()
    v = np.round(values, decimals)
    residual = round(target * len(v) - float(v.sum()), decimals)
    if abs(residual) > 0:
        # Adjust the largest free element that stays non-negative.
        order = [i for i in np.argsort(-v) if i not in protect and v[i] + residual >= 0]
        i = order[0]
        v[i] = round(v[i] + residual, decimals)
    assert abs(v.mean() - target) < 10 ** (-decimals) / 2, (v.mean(), target)
    return v


def _rain_field(shape: np.ndarray, peak: float, block_mean: float) -> np.ndarray:
    """v = max(0, (peak + b) * shape - b); solve b so mean(v) == block_mean (bisection)."""
    def mean_for(b: float) -> float:
        return float(np.maximum(0.0, (peak + b) * shape - b).mean())

    if mean_for(0.0) < block_mean:
        raise ValueError("Rain cell too narrow for the block mean; widen sigma")
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if mean_for(mid) > block_mean:
            lo = mid
        else:
            hi = mid
    b = (lo + hi) / 2
    return np.maximum(0.0, (peak + b) * shape - b)


# ---------------------------------------------------------------------------
# Build the dataset
# ---------------------------------------------------------------------------
def build_dataset() -> Dataset:
    rng = np.random.default_rng(RNG_SEED)
    ds = Dataset()

    # --- Hierarchy -----------------------------------------------------------
    ds.states.append({"id": 1, "lgd_code": "36", "name": "Telangana", "name_te": "తెలంగాణ", "name_hi": "तेलंगाना"})
    district_poly = Polygon(DISTRICT_OUTLINE)
    ds.districts.append({
        "id": 1, "lgd_code": "DEMO-D-SDP", "state_id": 1, "name": "Siddipet",
        "name_te": "సిద్దిపేట", "name_hi": "सिद्दीपेट", "geom": _as_multi(district_poly),
    })

    block_cells = _voronoi_cells([b[4] for b in BLOCK_SEEDS], district_poly)
    for i, (code, name, te, hi, _) in enumerate(BLOCK_SEEDS):
        ds.blocks.append({
            "id": i + 1, "lgd_code": code, "district_id": 1, "name": name, "name_te": te, "name_hi": hi,
            "mean_elevation_m": None, "geom": block_cells[i],
        })
    gajwel = ds.blocks[0]
    gajwel_poly = max(gajwel["geom"].geoms, key=lambda g: g.area)

    # --- Panchayats (Voronoi inside Gajwel) ----------------------------------
    pts = _poisson_points(gajwel_poly, len(GP_NAMES), min_km=2.4, rng=rng)
    cells = _voronoi_cells(pts, gajwel_poly)
    c = gajwel_poly.centroid
    lon0, lat0 = c.x, c.y

    # Put Ahmadipur on the GP closest to a point north-east of the block centre.
    ne = (lon0 + 0.05, lat0 + 0.04)
    demo_idx = min(range(len(pts)), key=lambda i: math.dist(pts[i], ne))
    names = list(GP_NAMES)
    names.remove((DEMO_GP, GP_NAMES[0][1]))
    names.insert(demo_idx, (DEMO_GP, GP_NAMES[0][1]))

    # Natural-looking boundaries (applied to all levels so shared edges still match).
    ds.districts[0]["geom"] = _as_multi(_warp(ds.districts[0]["geom"]))
    for b in ds.blocks:
        b["geom"] = _as_multi(_warp(b["geom"]))
    cells = [_as_multi(_warp(cell)) for cell in cells]
    # Block outline = union of its GPs, so GPs tile the block exactly.
    from shapely.ops import unary_union

    # Drop hairline holes where warped GP edges don't meet exactly.
    merged = _as_multi(unary_union(cells).buffer(1e-7).buffer(-1e-7))
    gajwel["geom"] = MultiPolygon([Polygon(p.exterior) for p in merged.geoms])

    for i, cell in enumerate(cells):
        cen = cell.centroid
        x, y = _km_xy(cen.x, cen.y, lon0, lat0)
        # Smooth terrain: higher to the north-west, gentle undulation.
        elev = 548 + 2.2 * (y - x) + 14 * math.sin(x / 3.1) * math.cos(y / 2.7) + rng.normal(0, 4)
        name, name_te = names[i]
        ds.panchayats.append({
            "id": i + 1, "lgd_code": f"DEMO-GP-{i + 1:03d}", "block_id": gajwel["id"],
            "name": name, "name_te": name_te, "name_hi": None,
            "elevation_m": round(elev, 0),
            "registered_farmers": DEMO_GP_FARMERS if name == DEMO_GP else int(rng.integers(120, 460)),
            "geom": cell, "centroid": Point(round(cen.x, 6), round(cen.y, 6)),
            "_xy": (x, y),
        })
    gps = ds.panchayats
    n = len(gps)
    demo = next(i for i, g in enumerate(gps) if g["name"] == DEMO_GP)
    elev = np.array([g["elevation_m"] for g in gps], dtype=float)
    mean_elev = float(elev.mean())
    gajwel["mean_elevation_m"] = round(mean_elev, 1)
    xy = np.array([g["_xy"] for g in gps])

    # --- Forecast run ----------------------------------------------------------
    ds.forecast_runs.append({
        "id": 1, "issued_at": ISSUED_AT.isoformat(), "source": "seed", "status": "ok", "duration_s": 212.0,
        "notes": "Synthetic demo seed (Phase 1). Replaced by the real replay run in Phase 7.",
    })

    for d in range(5):
        ds.block_forecasts.append({
            "id": d + 1, "run_id": 1, "block_id": gajwel["id"], "day": d + 1, "date": FORECAST_DATES[d].isoformat(),
            **{k: BLOCK_FC[k][d] for k in BLOCK_FC},
        })

    # --- Rain cells per day: (centre offset km from Ahmadipur or block centre, sigma km, peak mm)
    demo_xy = xy[demo]
    rain_cells = [
        (np.array([-6.0, -4.0]), 5.0, 11.0),   # Day 1: light showers in the south-west
        (demo_xy, 4.2, 38.0),                   # Day 2: heavy cell centred on Ahmadipur
        (np.array([3.0, -5.0]), 6.0, 16.0),    # Day 3
        (np.array([-8.0, 6.0]), 3.0, 4.0),     # Day 4: nearly dry
        (np.array([6.0, 2.0]), 4.0, 6.0),      # Day 5
    ]

    base_spread = rng.uniform(0.12, 0.62, n)
    base_spread[demo] = 0.12
    pf_id = 0
    for d in range(5):
        centre, sigma, peak = rain_cells[d]
        dist2 = ((xy - centre) ** 2).sum(axis=1)
        # Widen the cell until the block mean is reachable (keeps the field smooth).
        while True:
            shape = np.exp(-dist2 / (2 * sigma**2))
            shape = shape / (shape[demo] if d == 1 else shape.max())  # Day 2: Ahmadipur is the peak
            shape = np.minimum(shape, 1.0)
            if peak * shape.mean() > BLOCK_FC["rain_mm"][d] * 1.15:
                break
            sigma *= 1.1
        rain = _rain_field(shape, peak, BLOCK_FC["rain_mm"][d])
        protect = {demo} if d == 1 else set()
        rain = _fix_mean(rain, BLOCK_FC["rain_mm"][d], protect=protect)
        if d == 1:
            rain[demo] = 38.0
            rain = _fix_mean(rain, BLOCK_FC["rain_mm"][d], protect={demo})

        # Temperature: block value + lapse-rate correction + evaporative cooling where it rains.
        dz = elev - mean_elev
        tmax = BLOCK_FC["tmax"][d] - LAPSE_C_PER_M * dz - 0.06 * (rain - rain.mean()) + rng.normal(0, 0.25, n)
        tmin = BLOCK_FC["tmin"][d] - LAPSE_C_PER_M * dz - 0.02 * (rain - rain.mean()) + rng.normal(0, 0.2, n)
        tmax = _fix_mean(tmax - (tmax.mean() - BLOCK_FC["tmax"][d]), BLOCK_FC["tmax"][d])
        tmin = _fix_mean(tmin - (tmin.mean() - BLOCK_FC["tmin"][d]), BLOCK_FC["tmin"][d])

        rh_block = (BLOCK_FC["rh_max"][d] + BLOCK_FC["rh_min"][d]) / 2
        rh = rh_block + 0.35 * (rain - rain.mean()) + rng.normal(0, 1.2, n)
        rh = np.clip(rh - (rh.mean() - rh_block), 30, 100)
        rh = _fix_mean(rh, rh_block)

        wind = BLOCK_FC["wind_kmh"][d] * (1 + 0.004 * dz + rng.normal(0, 0.08, n))
        wind = _fix_mean(wind * BLOCK_FC["wind_kmh"][d] / wind.mean(), BLOCK_FC["wind_kmh"][d])

        for i in range(n):
            v = float(rain[i])
            p10 = min(0.95, 0.03 + 0.69 * (v / 38.0) ** 0.8)
            p25 = min(0.97, p10 + (0.12 + 0.03 * min(v, 10) if v > 0 else 0.07))
            spread = float(base_spread[i] + 0.04 * (d + 1))
            conf = "high" if spread < 0.35 else "medium" if spread < 0.6 else "low"
            pf_id += 1
            ds.panchayat_forecasts.append({
                "id": pf_id, "run_id": 1, "panchayat_id": gps[i]["id"], "day": d + 1,
                "date": FORECAST_DATES[d].isoformat(),
                "rain_mm": v, "rain_min": round(v * 0.55, 1), "rain_max": round(v * 1.5 + (0.8 if v == 0 else 0), 1),
                "rain_prob_2_5mm": round(p25, 2), "rain_prob_10mm": round(p10, 2),
                "tmax": float(tmax[i]), "tmin": float(tmin[i]), "rh": float(rh[i]), "wind_kmh": float(wind[i]),
                "confidence": conf, "model_spread": round(spread, 3),
            })

    # --- AWS stations (all held out of training) + 90 days of observations ------
    station_gps = rng.choice([i for i in range(n) if i != demo], size=7, replace=False).tolist() + [demo]
    obs_start = date(2025, 6, 1)
    event_date = date(2025, 8, 14)
    obs_id = 0
    for s, gi in enumerate(station_gps):
        g = gps[gi]
        lon = g["centroid"].x + rng.normal(0, 0.004)
        lat = g["centroid"].y + rng.normal(0, 0.004)
        ds.aws_stations.append({
            "id": s + 1, "code": f"DEMO-AWS-{s + 1:02d}", "name": f"{g['name']} AWS",
            "lat": round(lat, 5), "lon": round(lon, 5), "elevation_m": g["elevation_m"],
            "panchayat_id": g["id"], "used_in_training": False, "geom": Point(round(lon, 5), round(lat, 5)),
        })
        for k in range(90):
            day = obs_start + timedelta(days=k)
            wet = rng.random() < 0.45
            rain = float(np.round(rng.gamma(0.9, 9.0), 1)) if wet else 0.0
            if day == event_date and gi == demo:
                rain = 41.0
            tmax = 31.5 - LAPSE_C_PER_M * (g["elevation_m"] - mean_elev) - 0.05 * rain + rng.normal(0, 1.4)
            tmin = 23.2 - LAPSE_C_PER_M * (g["elevation_m"] - mean_elev) + rng.normal(0, 0.8)
            qc = 0
            r = rng.random()
            if r < 0.03:
                qc = 1  # gap filled (temperature interpolated)
            elif r < 0.04:
                qc = 2  # removed by range / consistency check
            obs_id += 1
            ds.observations.append({
                "id": obs_id, "station_id": s + 1, "date": day.isoformat(),
                "rain_mm": None if qc == 2 else rain,
                "tmax": None if qc == 2 else round(tmax, 1), "tmin": None if qc == 2 else round(tmin, 1),
                "rh": None if qc == 2 else round(float(np.clip(78 + 0.4 * rain + rng.normal(0, 6), 35, 100)), 0),
                "wind_kmh": None if qc == 2 else round(float(abs(rng.normal(9, 3))), 1),
                "qc_flag": qc,
            })
    demo_station = ds.aws_stations[-1]["id"]

    add_other_blocks(ds, pf_id)

    # --- PLACEHOLDER validation (replaced by real results in Phase 8) -----------
    period = "Jun-Sep 2025"
    placeholder_metrics = [
        ("tmax", None, "block_baseline", dict(rmse=2.4, bias=0.9, mae=1.9)),
        ("tmax", None, "panchayatcast", dict(rmse=1.7, bias=0.2, mae=1.3)),
        ("tmin", None, "block_baseline", dict(rmse=1.9, bias=0.6, mae=1.5)),
        ("tmin", None, "panchayatcast", dict(rmse=1.4, bias=0.1, mae=1.1)),
        ("rain", 10.0, "block_baseline", dict(pod=0.48, far=0.41, csi=0.36)),
        ("rain", 10.0, "panchayatcast", dict(pod=0.63, far=0.33, csi=0.48)),
    ]
    for i, (var, thr, method, m) in enumerate(placeholder_metrics):
        ds.validation_metrics.append({
            "id": i + 1, "variable": var, "period": period, "method": method, "threshold_mm": thr,
            "rmse": m.get("rmse"), "bias": m.get("bias"), "mae": m.get("mae"),
            "pod": m.get("pod"), "far": m.get("far"), "csi": m.get("csi"),
            "n_stations": len(ds.aws_stations), "n_samples": len(ds.aws_stations) * 90, "is_placeholder": True,
        })
    ds.backtest_events.append({
        "id": 1, "date": event_date.isoformat(), "station_id": demo_station,
        "observed_mm": 41.0, "block_mm": 6.0, "ours_mm": 35.0,
        "note": "PLACEHOLDER: replace with a real backtest event in Phase 8.", "is_placeholder": True,
    })

    for g in gps:
        g.pop("_xy", None)
    return ds


OSM_VILLAGES = BACKEND_DIR / "data" / "raw" / "osm_siddipet_villages.json"


def _osm_villages(poly: Polygon, max_n: int = 45, min_km: float = 1.2) -> list[dict]:
    """Real village names + locations inside `poly` from OpenStreetMap (data/raw, ODbL).
    Villages and towns first, hamlets only to reach 12. Telugu/Hindi names come from OSM when
    tagged, otherwise an automatic transliteration of the English name (approximate)."""
    if not OSM_VILLAGES.exists():
        return []
    from indic_transliteration import sanscript

    els = json.loads(OSM_VILLAGES.read_text(encoding="utf-8"))["elements"]
    rank = {"town": 0, "village": 1, "hamlet": 2}
    els = sorted((e for e in els if e.get("tags", {}).get("name") and poly.contains(Point(e["lon"], e["lat"]))),
                 key=lambda e: (rank.get(e["tags"].get("place"), 3), e["id"]))
    out, seen = [], set()
    for e in els:
        t = e["tags"]
        if t.get("place") == "hamlet" and len(out) >= 12:
            continue
        name = t["name"].strip()
        if name.lower() in seen or any(_km(e["lon"], e["lat"], o["lon"], o["lat"]) < min_km for o in out):
            continue
        seen.add(name.lower())
        roman = name.lower().replace(" ", "")
        out.append({"lon": e["lon"], "lat": e["lat"], "osm_id": e["id"], "name": name,
                    "name_te": _script(t.get("name:te"), "ఀ", "౿") or sanscript.transliterate(roman, sanscript.ITRANS, sanscript.TELUGU),
                    "name_hi": _script(t.get("name:hi"), "ऀ", "ॿ") or sanscript.transliterate(roman, sanscript.ITRANS, sanscript.DEVANAGARI)})
        if len(out) >= max_n:
            break
    return out


def _script(name: str | None, lo: str, hi: str) -> str | None:
    """OSM name only if it is really written in that script (some name:hi tags are Latin)."""
    return name if name and any(lo <= ch <= hi for ch in name) else None


def _km(lon1, lat1, lon2, lat2):
    return math.hypot((lon1 - lon2) * 111.32 * math.cos(math.radians(lat1)), (lat1 - lat2) * 110.57)


def add_other_blocks(ds: Dataset, pf_id: int) -> None:
    """Panchayats + synthetic forecasts for the other Siddipet blocks (Phase 10).
    Names and locations are real OpenStreetMap villages (data/raw/osm_siddipet_villages.json);
    boundaries are Voronoi areas around them (approximate). Falls back to "<Block> GP 01" placeholders."""
    gid = max(g["id"] for g in ds.panchayats)
    bf_id = max(b["id"] for b in ds.block_forecasts)
    for block in ds.blocks[1:]:
        rng = np.random.default_rng(RNG_SEED + block["id"])
        poly = max(block["geom"].geoms, key=lambda g: g.area)
        c = poly.centroid
        area_km2 = poly.area * 111.32 * math.cos(math.radians(c.y)) * 110.57
        n = int(np.clip(round(area_km2 / 18), 12, 40))
        villages = _osm_villages(poly)
        if len(villages) >= 8:
            pts = [(v["lon"], v["lat"]) for v in villages]
        else:
            villages = []
            pts = _poisson_points(poly, n, min_km=max(1.8, math.sqrt(area_km2 / n) * 0.55), rng=rng)
        cells = _voronoi_cells(pts, poly)
        block["mean_elevation_m"] = None
        gps, xy = [], []
        for i, cell in enumerate(cells):
            cen = cell.centroid
            x, y = _km_xy(cen.x, cen.y, c.x, c.y)
            elev = 520 + 2.0 * (y - x) + 12 * math.sin(x / 3.3) * math.cos(y / 2.9) + rng.normal(0, 4)
            gid += 1
            v = villages[i] if villages else None
            gps.append({"id": gid, "lgd_code": f"OSM-{v['osm_id']}" if v else f"DEMO-GP-{gid:03d}", "block_id": block["id"],
                        "name": v["name"] if v else f"{block['name']} GP {i + 1:02d}",
                        "name_te": v["name_te"] if v else f"{block['name_te']} పంచాయతీ {i + 1}",
                        "name_hi": v["name_hi"] if v else f"{block['name_hi']} पंचायत {i + 1}", "elevation_m": round(elev, 0),
                        "registered_farmers": int(rng.integers(120, 460)), "geom": cell,
                        "centroid": Point(round(cen.x, 6), round(cen.y, 6))})
            xy.append((x, y))
        ds.panchayats.extend(gps)
        xy = np.array(xy)
        elev = np.array([g["elevation_m"] for g in gps])
        block["mean_elevation_m"] = round(float(elev.mean()), 1)
        nb = len(gps)
        spread0 = rng.uniform(0.12, 0.62, nb)
        for d in range(5):
            bfc = {k: BLOCK_FC[k][d] for k in BLOCK_FC}
            bfc["rain_mm"] = round(float(BLOCK_FC["rain_mm"][d] * rng.uniform(0.4, 1.6)), 1)
            for k in ("tmax", "tmin"):
                bfc[k] = round(float(BLOCK_FC[k][d] + rng.normal(0, 0.6)), 1)
            bf_id += 1
            ds.block_forecasts.append({"id": bf_id, "run_id": 1, "block_id": block["id"], "day": d + 1,
                                       "date": FORECAST_DATES[d].isoformat(), **bfc})
            centre = xy[rng.integers(0, nb)]
            peak = max(bfc["rain_mm"] * rng.uniform(2.5, 4.0), bfc["rain_mm"] * 1.2 + 0.5)
            sigma = 6.0
            while True:  # widen the cell until the block mean is reachable
                shape = np.exp(-((xy - centre) ** 2).sum(axis=1) / (2 * sigma ** 2))
                shape = shape / shape.max()
                if peak * shape.mean() > bfc["rain_mm"] * 1.15:
                    break
                sigma *= 1.1
            rain = _rain_field(shape, peak, bfc["rain_mm"]) if bfc["rain_mm"] > 0 else np.zeros(nb)
            rain = _fix_mean(rain, bfc["rain_mm"])
            dz = elev - elev.mean()
            tmax = _fix_mean(bfc["tmax"] - LAPSE_C_PER_M * dz + rng.normal(0, 0.25, nb) - 0.06 * (rain - rain.mean()), bfc["tmax"])
            tmin = _fix_mean(bfc["tmin"] - LAPSE_C_PER_M * dz + rng.normal(0, 0.2, nb), bfc["tmin"])
            rh_b = (bfc["rh_max"] + bfc["rh_min"]) / 2
            rh = _fix_mean(np.clip(rh_b + 0.35 * (rain - rain.mean()) + rng.normal(0, 1.2, nb), 30, 100), rh_b)
            wind = bfc["wind_kmh"] * (1 + 0.004 * dz + rng.normal(0, 0.08, nb))
            wind = _fix_mean(wind * bfc["wind_kmh"] / wind.mean(), bfc["wind_kmh"])
            for i, g in enumerate(gps):
                v = float(rain[i])
                p10 = min(0.95, 0.03 + 0.69 * (v / 38.0) ** 0.8)
                spread = float(spread0[i] + 0.04 * (d + 1))
                pf_id += 1
                ds.panchayat_forecasts.append({
                    "id": pf_id, "run_id": 1, "panchayat_id": g["id"], "day": d + 1,
                    "date": FORECAST_DATES[d].isoformat(), "rain_mm": v, "rain_min": round(v * 0.55, 1),
                    "rain_max": round(v * 1.5 + (0.8 if v == 0 else 0), 1),
                    "rain_prob_2_5mm": round(min(0.97, p10 + (0.12 + 0.03 * min(v, 10) if v > 0 else 0.07)), 2),
                    "rain_prob_10mm": round(p10, 2), "tmax": float(tmax[i]), "tmin": float(min(tmin[i], tmax[i] - 0.5)),
                    "rh": float(rh[i]), "wind_kmh": float(wind[i]),
                    "confidence": "high" if spread < 0.35 else "medium" if spread < 0.6 else "low",
                    "model_spread": round(spread, 3),
                })


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def check_dataset(ds: Dataset) -> list[str]:
    """Return a list of human-readable check results. Raises AssertionError on failure."""
    msgs = []
    by_block = {b["id"]: [g for g in ds.panchayats if g["block_id"] == b["id"]] for b in ds.blocks}
    gps = by_block[ds.blocks[0]["id"]]
    assert len(gps) == 24, len(gps)
    assert sum(g["name"] == DEMO_GP for g in gps) == 1
    for b in ds.blocks:
        assert by_block[b["id"]], f"block {b['name']} has no panchayats"
        for g in by_block[b["id"]]:
            assert g["geom"].is_valid and not g["geom"].is_empty, g["name"]
            assert b["geom"].buffer(1e-6).contains(g["geom"]), g["name"]
    msgs.append(f"24 panchayats in {ds.blocks[0]['name']}; {len(ds.panchayats)} panchayats across all "
                f"{len(ds.blocks)} blocks, valid polygons inside their block")

    demo_id = next(g["id"] for g in gps if g["name"] == DEMO_GP)
    gp_block = {g["id"]: g["block_id"] for g in ds.panchayats}
    for b_id, d in [(b["id"], d) for b in ds.blocks for d in range(1, 6)]:
        rows = [r for r in ds.panchayat_forecasts if r["day"] == d and gp_block[r["panchayat_id"]] == b_id]
        bf = next(b for b in ds.block_forecasts if b["day"] == d and b["block_id"] == b_id)
        for var, target in [("rain_mm", bf["rain_mm"]), ("tmax", bf["tmax"]), ("tmin", bf["tmin"]),
                            ("rh", (bf["rh_max"] + bf["rh_min"]) / 2), ("wind_kmh", bf["wind_kmh"])]:
            mean = sum(r[var] for r in rows) / len(rows)
            assert abs(mean - target) < 0.05, (d, var, mean, target)
        assert all(r["tmax"] > r["tmin"] for r in rows)
        assert all(r["rain_mm"] >= 0 for r in rows)
    msgs.append("Mass consistency: panchayat mean == block value for every block, 5 days x 5 variables")

    d2 = [r for r in ds.panchayat_forecasts if r["day"] == 2 and gp_block[r["panchayat_id"]] == ds.blocks[0]["id"]]
    ah = next(r for r in d2 if r["panchayat_id"] == demo_id)
    assert ah["rain_mm"] == 38.0 and ah["rain_prob_10mm"] == 0.72 and ah["confidence"] == "high", ah
    lo, hi = min(r["rain_mm"] for r in d2), max(r["rain_mm"] for r in d2)
    assert lo == 0.0 and hi == 38.0, (lo, hi)
    msgs.append(f"Day 2: rain {lo:g}-{hi:g} mm across 24 GPs; block says 8 mm; Ahmadipur 38 mm @ 72%, high confidence")

    assert all(not s["used_in_training"] for s in ds.aws_stations)
    msgs.append(f"{len(ds.aws_stations)} AWS stations, none used in training; {len(ds.observations)} observations")
    conf = {c: sum(r["confidence"] == c for r in d2) for c in ("high", "medium", "low")}
    msgs.append(f"Day 2 confidence mix: {conf}")
    return msgs


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------
def _geojson(g):
    return mapping(g) if g is not None else None


def _row_json(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k in ("geom", "centroid"):
            out[k] = _geojson(v)
        else:
            out[k] = v
    return out


def write_demo_json(ds: Dataset, directory: Path = DEMO_DIR) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "regions.json": {
            "states": ds.states,
            "districts": [_row_json(r) for r in ds.districts],
            "blocks": [_row_json(r) for r in ds.blocks],
        },
        "panchayats.geojson": {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "id": g["id"], "geometry": _geojson(g["geom"]),
                 "properties": {k: (_geojson(v) if k == "centroid" else v) for k, v in g.items() if k != "geom"}}
                for g in ds.panchayats
            ],
        },
        "forecast.json": {
            "run": ds.forecast_runs[0],
            "block_forecasts": ds.block_forecasts,
            "panchayat_forecasts": ds.panchayat_forecasts,
        },
        "stations.json": {
            "stations": [_row_json(s) for s in ds.aws_stations],
            "observations": ds.observations,
        },
        "validation.json": {
            "metrics": ds.validation_metrics,
            "backtest_events": ds.backtest_events,
        },
    }
    paths = []
    for name, data in files.items():
        p = directory / name
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        paths.append(p)
    return paths


def _sql(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float, np.integer, np.floating)):
        return repr(float(v)) if isinstance(v, (float, np.floating)) else str(int(v))
    if hasattr(v, "geom_type"):
        return f"ST_GeomFromText('{shp_wkt.dumps(v, rounding_precision=6)}', 4326)"
    s = str(v).replace("'", "''")
    return f"'{s}'"


def _insert(table: str, rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return ""
    values = ",\n".join("(" + ", ".join(_sql(r.get(c)) for c in cols) + ")" for r in rows)
    return f"insert into {table} ({', '.join(cols)}) values\n{values};\n\n"


def build_seed_sql(ds: Dataset) -> str:
    parts = [
        "-- Kshetra demo seed. GENERATED by scripts/seed_demo.py - do not edit by hand.\n",
        "-- Run AFTER migrations/0001_schema.sql. WARNING: clears existing demo tables first.\n",
        "-- Boundaries are illustrative, forecasts synthetic, validation rows are placeholders.\n\n",
        "begin;\n\n",
        "truncate table states, forecast_runs, aws_stations, validation_metrics restart identity cascade;\n\n",
        _insert("states", ds.states, ["id", "lgd_code", "name", "name_te", "name_hi"]),
        _insert("districts", ds.districts, ["id", "lgd_code", "state_id", "name", "name_te", "name_hi", "geom"]),
        _insert("blocks", ds.blocks,
                ["id", "lgd_code", "district_id", "name", "name_te", "name_hi", "mean_elevation_m", "geom"]),
        _insert("panchayats", ds.panchayats,
                ["id", "lgd_code", "block_id", "name", "name_te", "name_hi", "elevation_m",
                 "registered_farmers", "geom", "centroid"]),
        _insert("forecast_runs", ds.forecast_runs, ["id", "issued_at", "source", "status", "duration_s", "notes"]),
        _insert("block_forecasts", ds.block_forecasts,
                ["id", "run_id", "block_id", "day", "date", "rain_mm", "tmax", "tmin", "rh_max", "rh_min",
                 "wind_kmh", "wind_dir", "cloud_okta"]),
        _insert("panchayat_forecasts", ds.panchayat_forecasts,
                ["id", "run_id", "panchayat_id", "day", "date", "rain_mm", "rain_min", "rain_max",
                 "rain_prob_2_5mm", "rain_prob_10mm", "tmax", "tmin", "rh", "wind_kmh", "confidence",
                 "model_spread"]),
        _insert("aws_stations", ds.aws_stations,
                ["id", "code", "name", "lat", "lon", "elevation_m", "panchayat_id", "used_in_training", "geom"]),
        _insert("observations", ds.observations,
                ["id", "station_id", "date", "rain_mm", "tmax", "tmin", "rh", "wind_kmh", "qc_flag"]),
        _insert("validation_metrics", ds.validation_metrics,
                ["id", "variable", "period", "method", "threshold_mm", "rmse", "bias", "mae", "pod", "far", "csi",
                 "n_stations", "n_samples", "is_placeholder"]),
        _insert("backtest_events", ds.backtest_events,
                ["id", "date", "station_id", "observed_mm", "block_mm", "ours_mm", "note", "is_placeholder"]),
    ]
    # Move sequences past the explicit ids so later inserts don't collide.
    for t in ["states", "districts", "blocks", "panchayats", "forecast_runs", "block_forecasts",
              "panchayat_forecasts", "aws_stations", "observations", "validation_metrics", "backtest_events"]:
        parts.append(f"select setval(pg_get_serial_sequence('{t}', 'id'), coalesce((select max(id) from {t}), 1));\n")
    parts.append("\ncommit;\n")
    return "".join(parts)


def apply_to_database(database_url: str, seed_sql: str) -> None:
    import psycopg

    with psycopg.connect(database_url, autocommit=True) as conn:
        for mig in sorted(MIGRATIONS_DIR.glob("*.sql")):
            print(f"  applying {mig.name}")
            conn.execute(mig.read_text(encoding="utf-8"))
        print("  applying seed.sql")
        conn.execute(seed_sql)
        n = conn.execute("select count(*) from panchayats").fetchone()[0]
        avg = conn.execute(
            "select round(avg(rain_mm)::numeric, 2) from panchayat_forecasts where day = 2"
        ).fetchone()[0]
        print(f"  database now has {n} panchayats; Day 2 mean rain = {avg} mm")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="run migrations + seed on DATABASE_URL")
    args = parser.parse_args()

    ds = build_dataset()
    print("Checks:")
    for m in check_dataset(ds):
        print(f"  OK  {m}")

    write_demo_json(ds, SEED_DIR)
    for p in write_demo_json(ds, DEMO_DIR):
        print(f"Wrote {p.relative_to(BACKEND_DIR)} ({p.stat().st_size / 1024:.0f} KB)")
    print(f"Wrote the same files to {SEED_DIR.relative_to(BACKEND_DIR)} (fixed copy for tests)")
    sql = build_seed_sql(ds)
    SEED_SQL.write_text(sql, encoding="utf-8")
    print(f"Wrote {SEED_SQL.relative_to(BACKEND_DIR)} ({len(sql) / 1024:.0f} KB)")

    if args.apply:
        from app.core.config import get_settings

        url = get_settings().database_url
        if not url:
            raise SystemExit("DATABASE_URL is not set in backend/.env (Supabase > Project Settings > Database)")
        print("Applying to database:")
        apply_to_database(url, sql)


if __name__ == "__main__":
    main()
