"""Find good replay events: past monsoon days when rain varied most across the block.

Uses ECMWF IFS (~9 km) rain at 0.1° points inside the block (Open-Meteo archive). A good demo day has
heavy rain in part of the block, little elsewhere, and a modest block average - exactly the case
where "copy the block value" misleads farmers.

Usage (from backend/):  .venv/Scripts/python -m pipeline.find_replay [--years 2023 2024 2025]
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from pipeline import openmeteo
from pipeline.common import config
from pipeline.grid import load_block
from pipeline.train import grid_points


def candidates(years: list[int], top: int = 8) -> pd.DataFrame:
    cfg = config()
    block, _ = load_block(cfg["block_id"])
    minx, miny, maxx, maxy = block["shape"].bounds
    lats, lons = grid_points(miny - 0.05, maxy + 0.05, 0.1), grid_points(minx - 0.05, maxx + 0.05, 0.1)
    LA, LO = np.meshgrid(lats, lons, indexing="ij")
    frames = []
    for y in years:
        res = openmeteo.multi("archive", LA.ravel().tolist(), LO.ravel().tolist(), {
            "start_date": f"{y}-06-01", "end_date": f"{y}-09-30", "daily": "precipitation_sum",
            "models": cfg["training"]["fine_rain_model"], "timezone": cfg["timezone"]}, chunk=25, raw_grid=True)
        rain = np.array([r["daily"]["precipitation_sum"] for r in res], dtype=float)
        frames.append(pd.DataFrame({
            "date": res[0]["daily"]["time"], "block_mean": np.nanmean(rain, axis=0),
            "max": np.nanmax(rain, axis=0), "min": np.nanmin(rain, axis=0)}))
    df = pd.concat(frames, ignore_index=True)
    df["spread"] = df["max"] - df["min"]
    good = df[(df["max"] >= 30) & (df["block_mean"].between(4, 35))].copy()
    good["score"] = good["spread"] / (good["block_mean"] + 5)
    return good.sort_values("score", ascending=False).head(top).round(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025])
    args = ap.parse_args()
    c = candidates(args.years)
    print("Best replay candidates (ECMWF IFS ~9 km rain at points inside the block, mm/day):")
    print(c.to_string(index=False))
    if len(c):
        from datetime import date, timedelta

        d = date.fromisoformat(c.iloc[0]["date"]) - timedelta(days=1)
        print(f"\nSuggested: issue the replay the day before the event so it is Day 2 of the forecast:\n"
              f"  .venv/Scripts/python -m pipeline.run_daily --replay {d.isoformat()} --publish-demo")


if __name__ == "__main__":
    main()
