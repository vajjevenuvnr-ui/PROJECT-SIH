"""Builds forecast responses (summary, GeoJSON, insight, panchayat detail) from a DataSource."""

from __future__ import annotations

from datetime import date as date_cls

from fastapi import HTTPException

from app.core.datasource import DataSource
from app.core.imd import VARIABLES, alerts_for_day, block_value, rain_category, source_label
from app.services.warnings import RANK, sort_key, warnings_for_day

CONF_RANK = {"high": 0, "medium": 1, "low": 2}


def _weekday(iso: str) -> str:
    return date_cls.fromisoformat(iso).strftime("%a")


def _num(v):
    return None if v is None else round(float(v), 2)


def _centroid(gp: dict) -> list[float] | None:
    c = gp.get("centroid")
    if isinstance(c, dict) and c.get("coordinates"):
        return [round(c["coordinates"][0], 6), round(c["coordinates"][1], 6)]
    return None


def region(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {k: row.get(k) for k in ("id", "lgd_code", "name", "name_te", "name_hi")}


def run_info(run: dict | None) -> dict | None:
    if run is None:
        return None
    return {
        "id": run["id"], "issued_at": run["issued_at"], "source": run["source"],
        "source_label": source_label(run["source"]), "status": run["status"], "duration_s": run.get("duration_s"),
    }


def require_block(ds: DataSource, block_id: int) -> dict:
    block = ds.get_block(block_id)
    if block is None:
        raise HTTPException(404, f"Block {block_id} not found")
    return block


def require_run(ds: DataSource) -> dict:
    run = ds.latest_run()
    if run is None:
        raise HTTPException(503, "No forecast run available yet")
    return run


def _check_day(day: int) -> None:
    if day not in range(1, 6):
        raise HTTPException(422, "day must be between 1 and 5")


def block_bundle(ds: DataSource, block_id: int) -> tuple[dict, dict, list[dict], list[dict], list[dict]]:
    """(block, run, panchayats, block_forecasts, panchayat_forecasts) for the latest run."""
    block = require_block(ds, block_id)
    run = require_run(ds)
    gps = ds.list_panchayats(block_id)
    bfc = ds.block_forecasts(run["id"], block_id)
    pfc = ds.panchayat_forecasts(run["id"], [g["id"] for g in gps]) if gps else []
    return block, run, gps, bfc, pfc


# ---------------------------------------------------------------------------
# S1 summary
# ---------------------------------------------------------------------------
def block_summary(ds: DataSource, block_id: int) -> dict:
    block, run, gps, bfc, pfc = block_bundle(ds, block_id)
    names = {g["id"]: g["name"] for g in gps}
    by_id = {g["id"]: g for g in gps}
    alerts, warnings = [], []
    for row in sorted(pfc, key=lambda r: (r["day"], r["panchayat_id"])):
        for a in alerts_for_day(row):
            alerts.append({**a.as_dict(), "panchayat_id": row["panchayat_id"],
                           "panchayat_name": names.get(row["panchayat_id"])})
        warnings += warnings_for_day(row, by_id[row["panchayat_id"]], run)
    return {
        "block": region(block),
        "district": region(ds.get_district(block["district_id"])),
        "panchayat_count": len(gps),
        "active_alerts": len(alerts),
        "alerts": alerts,
        "warnings": sorted(warnings, key=sort_key),
        "run": run_info(run),
        "days": [{"day": b["day"], "date": b["date"], "weekday": _weekday(b["date"])}
                 for b in sorted(bfc, key=lambda b: b["day"])],
    }


# ---------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------
def feature(geom: dict | None, props: dict, fid=None) -> dict:
    f = {"type": "Feature", "geometry": geom, "properties": props}
    if fid is not None:
        f["id"] = fid
    return f


def block_geojson(ds: DataSource, block_id: int) -> dict:
    block = require_block(ds, block_id)
    props = {**region(block), "mean_elevation_m": block.get("mean_elevation_m")}
    return {"type": "FeatureCollection", "features": [feature(block.get("geom"), props, block["id"])]}


def district_blocks_geojson(ds: DataSource, district_id: int) -> dict:
    district = ds.get_district(district_id)
    if district is None:
        raise HTTPException(404, f"District {district_id} not found")
    feats = [feature(district.get("geom"), {**region(district), "kind": "district"}, f"d{district['id']}")]
    for b in ds.list_blocks(district_id):
        feats.append(feature(b.get("geom"), {**region(b), "kind": "block"}, b["id"]))
    return {"type": "FeatureCollection", "features": feats}


def panchayats_geojson(ds: DataSource, block_id: int, var: str, day: int) -> dict:
    _check_day(day)
    block, run, gps, bfc, pfc = block_bundle(ds, block_id)
    col = VARIABLES[var]["column"]
    by_gp = {r["panchayat_id"]: r for r in pfc if r["day"] == day}
    bday = next((b for b in bfc if b["day"] == day), None)
    feats = []
    for g in gps:
        r = by_gp.get(g["id"])
        if r is None:
            continue
        value = r.get(col)
        props = {
            "id": g["id"], "name": g["name"], "name_te": g.get("name_te"), "name_hi": g.get("name_hi"),
            "elevation_m": g.get("elevation_m"), "value": _num(value),
            "min": _num(r.get("rain_min")) if var == "rain" else _num(value),
            "max": _num(r.get("rain_max")) if var == "rain" else _num(value),
            "rain_mm": _num(r.get("rain_mm")), "rain_prob_10mm": r.get("rain_prob_10mm"),
            "confidence": r["confidence"],
        }
        if var == "rain":
            props["category"] = rain_category(value)
        feats.append(feature(g.get("geom"), props, g["id"]))
    return {
        "type": "FeatureCollection",
        "features": feats,
        "meta": {
            "variable": var, "unit": VARIABLES[var]["unit"], "day": day,
            "date": bday["date"] if bday else None,
            "block_value": _num(block_value(bday, var)) if bday else None,
            "run": run_info(run),
        },
    }


def panchayats_forecast_bundle(ds: DataSource, block_id: int) -> dict:
    """All panchayats x 5 days x 5 variables plus the block outline and block values in one response,
    so the S2 map can switch variable/day instantly without further requests."""
    block, run, gps, bfc, pfc = block_bundle(ds, block_id)
    by_gp: dict[int, list[dict]] = {}
    for r in sorted(pfc, key=lambda r: r["day"]):
        by_gp.setdefault(r["panchayat_id"], []).append({
            "day": r["day"],
            "rain": _num(r["rain_mm"]), "rain_min": _num(r.get("rain_min")), "rain_max": _num(r.get("rain_max")),
            "rain_prob_10mm": r.get("rain_prob_10mm"), "rain_prob_2_5mm": r.get("rain_prob_2_5mm"),
            "tmax": _num(r["tmax"]), "tmin": _num(r["tmin"]), "rh": _num(r.get("rh")), "wind": _num(r.get("wind_kmh")),
            "confidence": r["confidence"],
        })
    feats = [
        feature(g.get("geom"), {
            "id": g["id"], "name": g["name"], "name_te": g.get("name_te"), "name_hi": g.get("name_hi"),
            "elevation_m": g.get("elevation_m"), "days": by_gp.get(g["id"], []),
        }, g["id"])
        for g in gps if g["id"] in by_gp
    ]
    bdays = sorted(bfc, key=lambda b: b["day"])
    return {
        "type": "FeatureCollection",
        "features": feats,
        "meta": {
            "block": {**region(block), "district_id": block.get("district_id"),
                      "mean_elevation_m": block.get("mean_elevation_m")},
            "block_geometry": block.get("geom"),
            "run": run_info(run),
            "days": [{"day": b["day"], "date": b["date"], "weekday": _weekday(b["date"])} for b in bdays],
            "block_values": [
                {"day": b["day"], **{v: _num(block_value(b, v)) for v in VARIABLES}} for b in bdays
            ],
            "units": {v: VARIABLES[v]["unit"] for v in VARIABLES},
        },
    }


# ---------------------------------------------------------------------------
# Block values and insight
# ---------------------------------------------------------------------------
def block_forecast(ds: DataSource, block_id: int, day: int | None) -> dict:
    block = require_block(ds, block_id)
    run = require_run(ds)
    rows = sorted(ds.block_forecasts(run["id"], block_id), key=lambda r: r["day"])
    if day is not None:
        _check_day(day)
        rows = [r for r in rows if r["day"] == day]
    for r in rows:
        r["weekday"] = _weekday(r["date"])
        r["rain_category"] = rain_category(r.get("rain_mm"))
    return {"block": region(block), "run": run_info(run), "days": rows}


def insight(ds: DataSource, block_id: int, var: str, day: int) -> dict:
    _check_day(day)
    block, run, gps, bfc, pfc = block_bundle(ds, block_id)
    col, unit, label = VARIABLES[var]["column"], VARIABLES[var]["unit"], VARIABLES[var]["label"]
    vals = [r[col] for r in pfc if r["day"] == day and r.get(col) is not None]
    if not vals:
        raise HTTPException(404, "No panchayat forecasts for this block/day")
    bday = next((b for b in bfc if b["day"] == day), None)
    bval = block_value(bday, var) if bday else None
    lo, hi = min(vals), max(vals)
    sep = "" if unit in ("%",) else " "
    rng = f"{lo:g}-{hi:g}{sep}{unit}"
    text = f"{label} varies {rng} across {len(vals)} GPs"
    if bval is not None:
        text += f"; block says {bval:g}{sep}{unit}"
    return {"variable": var, "day": day, "unit": unit, "min": _num(lo), "max": _num(hi),
            "block_value": _num(bval), "n_panchayats": len(vals), "text": text}


# ---------------------------------------------------------------------------
# S3 panchayat detail
# ---------------------------------------------------------------------------
def panchayat_forecast(ds: DataSource, panchayat_id: int) -> dict:
    gp = ds.get_panchayat(panchayat_id)
    if gp is None:
        raise HTTPException(404, f"Panchayat {panchayat_id} not found")
    block = require_block(ds, gp["block_id"])
    run = require_run(ds)
    rows = sorted(ds.panchayat_forecasts(run["id"], [panchayat_id]), key=lambda r: r["day"])
    if not rows:
        raise HTTPException(404, "No forecast for this panchayat in the latest run")
    bfc = {b["day"]: b for b in ds.block_forecasts(run["id"], block["id"])}

    days, alerts, warnings = [], [], []
    for r in rows:
        b = bfc.get(r["day"], {})
        bvals = {"rain_mm": b.get("rain_mm"), "tmax": b.get("tmax"), "tmin": b.get("tmin"),
                 "rh": block_value(b, "rh") if b else None, "wind_kmh": b.get("wind_kmh")}
        diff = {k: (_num(r[k] - v) if r.get(k) is not None and v is not None else None) for k, v in bvals.items()}
        days.append({
            "day": r["day"], "date": r["date"], "weekday": _weekday(r["date"]),
            "rain_mm": r["rain_mm"], "rain_min": r.get("rain_min"), "rain_max": r.get("rain_max"),
            "rain_prob_2_5mm": r.get("rain_prob_2_5mm"), "rain_prob_10mm": r.get("rain_prob_10mm"),
            "rain_category": rain_category(r["rain_mm"]),
            "tmax": r["tmax"], "tmin": r["tmin"], "rh": r.get("rh"), "wind_kmh": r.get("wind_kmh"),
            "confidence": r["confidence"], "block": bvals, "diff": diff,
        })
        alerts += [{**a.as_dict(), "panchayat_id": panchayat_id, "panchayat_name": gp["name"]}
                   for a in alerts_for_day(r)]
        warnings += warnings_for_day(r, gp, run)

    worst = max((d["confidence"] for d in days[:3]), key=lambda c: CONF_RANK[c])
    info = {
        "id": gp["id"], "lgd_code": gp["lgd_code"], "name": gp["name"], "name_te": gp.get("name_te"),
        "name_hi": gp.get("name_hi"), "elevation_m": gp.get("elevation_m"),
        "registered_farmers": gp.get("registered_farmers"), "centroid": _centroid(gp),
        "block": region(block), "confidence": worst,
    }
    warnings.sort(key=lambda w: (-RANK[w["level"]], w["day"]))
    return {"panchayat": info, "run": run_info(run), "days": days, "alerts": alerts, "warnings": warnings}
