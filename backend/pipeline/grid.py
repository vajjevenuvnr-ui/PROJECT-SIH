"""Block / panchayat geometry and the 1 km downscaling grid (UTM 44N)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform
from shapely.prepared import prep

from pipeline.common import config

_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
_TO_LL = Transformer.from_crs("EPSG:32644", "EPSG:4326", always_xy=True)


def load_block(block_id: int) -> tuple[dict, list[dict]]:
    """Block record and its panchayats (with shapely geometry) from the demo boundary files.
    Boundaries are static, so the pipeline reads them from data/demo (same ids as the database)."""
    demo = config()["paths"]["demo"]
    regions = json.loads((demo / "regions.json").read_text(encoding="utf-8"))
    block = next(b for b in regions["blocks"] if b["id"] == block_id)
    block = {**block, "shape": shape(block["geom"])}
    feats = json.loads((demo / "panchayats.geojson").read_text(encoding="utf-8"))["features"]
    gps = [{**f["properties"], "shape": shape(f["geometry"])} for f in feats if f["properties"]["block_id"] == block_id]
    return block, gps


def to_utm(geom):
    return transform(_TO_UTM.transform, geom)


def cells_for_block(block: dict, gps: list[dict], km: float) -> pd.DataFrame:
    """1 km cell centres inside the block, each assigned to the panchayat containing it.
    Tiny panchayats with no cell centre get one extra cell at their centroid."""
    step = km * 1000
    b_utm = to_utm(block["shape"])
    gp_utm = [(g["id"], prep(to_utm(g["shape"]))) for g in gps]
    minx, miny, maxx, maxy = b_utm.bounds
    xs = np.arange(np.floor(minx / step) * step + step / 2, maxx, step)
    ys = np.arange(np.floor(miny / step) * step + step / 2, maxy, step)
    rows = []
    for y in ys:
        for x in xs:
            pt = Point(x, y)
            gid = next((gid for gid, g in gp_utm if g.contains(pt)), None)
            if gid is not None:
                rows.append((x, y, gid, False))
    have = {r[2] for r in rows}
    for g in gps:
        if g["id"] not in have:
            c = to_utm(g["shape"]).representative_point()
            rows.append((c.x, c.y, g["id"], True))
    df = pd.DataFrame(rows, columns=["x", "y", "gp_id", "extra"])
    lon, lat = _TO_LL.transform(df["x"].to_numpy(), df["y"].to_numpy())
    df["lon"], df["lat"] = lon, lat
    return df


def rect_grid(bounds_ll: tuple[float, float, float, float], km: float, margin_km: float):
    """Regular UTM grid (for DEM derivatives) covering bounds + margin. Returns x, y, lon, lat 2-D arrays."""
    step = km * 1000
    x0, y0 = _TO_UTM.transform(bounds_ll[0], bounds_ll[1])
    x1, y1 = _TO_UTM.transform(bounds_ll[2], bounds_ll[3])
    m = margin_km * 1000
    xs = np.arange(np.floor((x0 - m) / step) * step + step / 2, x1 + m, step)
    ys = np.arange(np.floor((y0 - m) / step) * step + step / 2, y1 + m, step)
    X, Y = np.meshgrid(xs, ys)
    lon, lat = _TO_LL.transform(X, Y)
    return X, Y, lon, lat


def forecast_points(block: dict, spacing_km: float) -> list[tuple[float, float]]:
    """Points inside the block where the model forecast is sampled; their mean = the block value."""
    b_utm = to_utm(block["shape"])
    minx, miny, maxx, maxy = b_utm.bounds
    step = spacing_km * 1000
    pts = []
    for y in np.arange(miny + step / 2, maxy, step):
        for x in np.arange(minx + step / 2, maxx, step):
            if b_utm.contains(Point(x, y)):
                lon, lat = _TO_LL.transform(x, y)
                pts.append((float(lat), float(lon)))
    if len(pts) < 4:  # small block: fall back to a denser sampling
        return forecast_points(block, spacing_km / 2) if spacing_km > 2 else pts + [
            (block["shape"].centroid.y, block["shape"].centroid.x)]
    return pts
