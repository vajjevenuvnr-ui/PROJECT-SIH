"""Daily pipeline: ingest -> static features (cached) -> downscale -> aggregate -> publish.

Usage (from backend/):
  .venv/Scripts/python -m pipeline.run_daily                         # live forecast from today
  .venv/Scripts/python -m pipeline.run_daily --replay 2024-08-31     # archived forecast of a past event
  add --publish-demo to make the run the data served in Demo Mode (data/demo/forecast.json)
  (the synthetic seed can be restored any time with: python -m scripts.seed_demo)

Writes data/runs/<source>-<date>.json and, when DATABASE_URL is set, inserts the run into Postgres.
Must finish in under 5 minutes for one district (network-bound; cached calls are instant).
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone

import numpy as np

from pipeline.common import Timer, config
from pipeline.downscale import downscale
from pipeline.features import static_cells
from pipeline.grid import forecast_points, load_block
from pipeline.ingest import block_bulletin, ingest_openmeteo

IST = timezone(timedelta(hours=5, minutes=30))


def all_block_ids() -> list[int]:
    """Blocks that have panchayat boundaries (Phase 10: every Siddipet block)."""
    feats = json.loads((config()["paths"]["demo"] / "panchayats.geojson").read_text(encoding="utf-8"))["features"]
    return sorted({f["properties"]["block_id"] for f in feats})


def run(replay: date | None = None, publish_demo: bool = False, block_id: int | None = None, quiet: bool = False) -> dict:
    cfg = config()
    block_ids = [block_id] if block_id else all_block_ids()
    timer = Timer()
    say = (lambda *a: None) if quiet else print
    say(f"Kshetra pipeline - {'replay ' + replay.isoformat() if replay else 'live forecast'} - "
        f"{len(block_ids)} block(s)")
    issued = (datetime.combine(replay, datetime.min.time(), IST).replace(hour=6) if replay
              else datetime.now(IST).replace(minute=0, second=0, microsecond=0))
    run_id = int(issued.strftime("%Y%m%d")) + (1_000_000_000 if replay else 0)

    rows, block_rows, n_points, n_cells, stale = [], [], 0, 0, False
    feed = None
    for b_id in block_ids:
        with timer.step(f"block {b_id}: static grid (cached) + forecast + downscale"):
            cells = static_cells(b_id)
            block, gps = load_block(b_id)
            points = forecast_points(block, cfg["forecast"]["point_spacing_km"])
            feed = ingest_openmeteo(points, start=replay)
            bulletin = block_bulletin(feed)
            rows += downscale(feed, bulletin, cells, run_id)
            block_rows += [{"run_id": run_id, "block_id": b_id, **b} for b in bulletin]
            n_points, n_cells, stale = n_points + len(points), n_cells + len(cells), stale or feed.stale
    for k, r in enumerate(rows, start=1):
        r["id"] = k
    for k, r in enumerate(block_rows, start=1):
        r["id"] = k

    members = [m for m in [feed.official, *cfg["forecast"]["ensemble_models"]] if feed.available(m)]
    source = "replay" if replay else "openmeteo-imd-format"
    run_rec = {
        "id": run_id, "issued_at": issued.isoformat(), "source": source,
        "status": "stale" if stale else "ok", "duration_s": round(timer.total, 1),
        "notes": (f"Open-Meteo {'historical forecast (archived)' if replay else 'forecast'}; official model "
                  f"{feed.official}; ensemble {', '.join(members)}; {len(block_ids)} blocks, {n_points} block points, "
                  f"{n_cells} x 1 km cells. Downscaled with lapse-rate + XGBoost (ERA5 -> ERA5-Land / ECMWF)."),
    }
    out = {"run": run_rec, "block_forecasts": block_rows, "panchayat_forecasts": rows}
    check(out)

    runs_dir = cfg["paths"]["runs"]
    path = runs_dir / f"{source}-{issued.date().isoformat()}.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    if publish_demo:
        demo_fc = cfg["paths"]["demo"] / "forecast.json"
        try:
            old = json.loads(demo_fc.read_text(encoding="utf-8"))
            if old["run"]["id"] != run_id:
                out["previous"] = {"run": old["run"], "panchayat_forecasts": old["panchayat_forecasts"]}
            elif old.get("previous"):
                out["previous"] = old["previous"]
        except (OSError, ValueError, KeyError):
            pass
        demo_fc.write_text(json.dumps(out, indent=1), encoding="utf-8")
    published_db = publish_database(out)

    if not quiet:
        report(out, members, stale)
        print("\nTimings:\n" + timer.report())
        print(f"\nSaved {path.relative_to(cfg['paths']['runs'].parents[1])}"
              + ("; published to Demo Mode (data/demo/forecast.json)" if publish_demo else "")
              + ("; inserted into the database" if published_db else ""))
    return {"run": run_rec, "path": str(path), "published_demo": publish_demo, "published_db": published_db,
            "timings": timer.steps}


def check(out: dict) -> None:
    """Sanity checks before publishing: mass consistency, no NaNs, Tmax > Tmin."""
    gp_block = _gp_blocks()
    for b in out["block_forecasts"]:
        rows = [r for r in out["panchayat_forecasts"] if r["day"] == b["day"] and gp_block.get(r.get("panchayat_id"), b.get("block_id")) == b.get("block_id")]
        for var, target in (("rain_mm", b["rain_mm"]), ("tmax", b["tmax"]), ("tmin", b["tmin"]), ("wind_kmh", b["wind_kmh"])):
            vals = np.array([r[var] for r in rows], dtype=float)
            assert np.isfinite(vals).all(), f"NaN in {var} day {b['day']}"
            assert abs(vals.mean() - target) < 0.1, f"mass consistency failed: {var} day {b['day']} {vals.mean()} vs {target}"
        assert all(r["tmax"] > r["tmin"] for r in rows), f"Tmax <= Tmin on day {b['day']}"
        assert all(r["rain_mm"] >= 0 for r in rows)


def _gp_blocks() -> dict[int, int]:
    try:
        feats = json.loads((config()["paths"]["demo"] / "panchayats.geojson").read_text(encoding="utf-8"))["features"]
        return {f["properties"]["id"]: f["properties"]["block_id"] for f in feats}
    except (OSError, ValueError):
        return {}


def report(out: dict, members: list[str], stale: bool) -> None:
    print(f"\nRun {out['run']['id']} ({out['run']['source']}, {out['run']['status']}); ensemble: {', '.join(members)}"
          + ("  [STALE: served from cache]" if stale else ""))
    print(f"    {'day':<12}{'block rain':>11}{'GP rain range':>16}{'block Tmax':>12}{'GP Tmax range':>16}  confidence")
    gp_block = _gp_blocks()
    for b in out["block_forecasts"]:
        if b["block_id"] != out["block_forecasts"][0]["block_id"] and b["day"] != 2:
            continue  # full table for the first block; Day 2 only for the others
        rows = [r for r in out["panchayat_forecasts"] if r["day"] == b["day"] and gp_block.get(r["panchayat_id"]) == b["block_id"]]
        rain = [r["rain_mm"] for r in rows]
        tmax = [r["tmax"] for r in rows]
        conf = {c: sum(r["confidence"] == c for r in rows) for c in ("high", "medium", "low")}
        print(f"    B{b['block_id']} {b['date']:<12}{b['rain_mm']:>9.1f} mm{min(rain):>8.1f}-{max(rain):<5.1f} mm"
              f"{b['tmax']:>10.1f} °C{min(tmax):>8.1f}-{max(tmax):<5.1f} °C  "
              f"H{conf['high']} M{conf['medium']} L{conf['low']}")


def publish_database(out: dict) -> bool:
    """Insert the run into Postgres/Supabase when DATABASE_URL is configured (else skip)."""
    from app.core.config import get_settings

    url = get_settings().database_url
    if not url:
        return False
    import psycopg

    r = out["run"]
    with psycopg.connect(url) as conn:
        conn.execute("delete from forecast_runs where id = %s", (r["id"],))
        conn.execute("insert into forecast_runs (id, issued_at, source, status, duration_s, notes) values (%s,%s,%s,%s,%s,%s)",
                     (r["id"], r["issued_at"], r["source"], r["status"], r["duration_s"], r["notes"]))
        cols = ["run_id", "block_id", "day", "date", "rain_mm", "tmax", "tmin", "rh_max", "rh_min", "wind_kmh",
                "wind_dir", "cloud_okta"]
        for b in out["block_forecasts"]:
            conn.execute(f"insert into block_forecasts ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})",
                         [b[c] for c in cols])
        cols = ["run_id", "panchayat_id", "day", "date", "rain_mm", "rain_min", "rain_max", "rain_prob_2_5mm",
                "rain_prob_10mm", "tmax", "tmin", "rh", "wind_kmh", "confidence", "model_spread"]
        with conn.cursor() as cur:
            cur.executemany(f"insert into panchayat_forecasts ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})",
                            [[p[c] for c in cols] for p in out["panchayat_forecasts"]])
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replay", type=date.fromisoformat, help="issue date of a past event to replay (YYYY-MM-DD)")
    ap.add_argument("--publish-demo", action="store_true", help="serve this run in Demo Mode")
    args = ap.parse_args()
    run(replay=args.replay, publish_demo=args.publish_demo)


if __name__ == "__main__":
    main()
