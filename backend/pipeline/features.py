"""Static features on the 1 km grid: elevation (Copernicus DEM 90 m), slope, aspect, TPI.

Computed once per block and cached in data/static/. LULC / NDVI / distance-to-water are listed in the
Data Strategy but need large downloads; they are not used yet (see pipeline/README.md).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter

from pipeline import openmeteo
from pipeline.common import config
from pipeline.grid import cells_for_block, load_block, rect_grid


def static_cells(block_id: int | None = None, force: bool = False) -> pd.DataFrame:
    cfg = config()
    block_id = block_id or cfg["block_id"]
    out = cfg["paths"]["static"] / f"cells_block{block_id}_{cfg['grid_km']:g}km.csv"
    if out.exists() and not force:
        cached = pd.read_csv(out)
        block, gps = load_block(block_id)
        if set(cached["gp_id"]) == {g["id"] for g in gps}:
            return cached
        return _reassign(cached, block, gps, cfg["grid_km"], out)

    block, gps = load_block(block_id)
    cells = cells_for_block(block, gps, cfg["grid_km"])

    # DEM on a regular grid (with margin) for slope / TPI, then sample at the cells.
    X, Y, lon, lat = rect_grid(block["shape"].bounds, cfg["grid_km"], margin_km=2)
    z = np.array(openmeteo.elevation(lat.ravel().tolist(), lon.ravel().tolist())).reshape(X.shape)
    step = cfg["grid_km"] * 1000
    dzdy, dzdx = np.gradient(z, step)
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = np.arctan2(-dzdx, dzdy)  # radians, 0 = north-facing
    tpi = z - uniform_filter(z, size=5, mode="nearest")  # >0 ridge / hilltop, <0 valley

    # nearest regular-grid node for each cell
    ix = np.clip(np.round((cells["x"].to_numpy() - X[0, 0]) / step).astype(int), 0, X.shape[1] - 1)
    iy = np.clip(np.round((cells["y"].to_numpy() - Y[0, 0]) / step).astype(int), 0, X.shape[0] - 1)
    # Cells sit on the same 1 km lattice as the DEM grid; only extra centroid cells need their own lookup.
    cells["elev"] = z[iy, ix]
    extra = cells.index[cells["extra"]]
    if len(extra):
        cells.loc[extra, "elev"] = openmeteo.elevation(cells.loc[extra, "lat"].tolist(), cells.loc[extra, "lon"].tolist())
    cells["slope_deg"] = slope[iy, ix]
    cells["aspect_sin"], cells["aspect_cos"] = np.sin(aspect[iy, ix]), np.cos(aspect[iy, ix])
    cells["tpi"] = tpi[iy, ix]
    cells = cells.round({"lat": 5, "lon": 5, "elev": 1, "slope_deg": 2, "aspect_sin": 3, "aspect_cos": 3, "tpi": 1})
    cells.to_csv(out, index=False)
    return cells


TERRAIN = ["elev", "slope_deg", "aspect_sin", "aspect_cos", "tpi"]


def _reassign(cached: pd.DataFrame, block, gps, grid_km: float, out) -> pd.DataFrame:
    """Panchayats changed (e.g. new boundaries) but the block did not: re-link cells to panchayats and
    reuse the cached terrain, so the DEM is not downloaded again. Only new centroid cells need elevation."""
    cells = cells_for_block(block, gps, grid_km)
    lattice = cached[~cached["extra"]].set_index(["x", "y"])[TERRAIN]
    cells = cells.join(lattice, on=["x", "y"])
    miss = cells.index[cells["elev"].isna()]
    if len(miss):
        src = cached[~cached["extra"]]
        for i in miss:  # terrain shape from the nearest cached lattice cell
            j = ((src["x"] - cells.at[i, "x"]) ** 2 + (src["y"] - cells.at[i, "y"]) ** 2).idxmin()
            cells.loc[i, TERRAIN] = src.loc[j, TERRAIN].to_numpy()
        cells.loc[miss, "elev"] = openmeteo.elevation(cells.loc[miss, "lat"].tolist(), cells.loc[miss, "lon"].tolist())
    cells = cells.round({"lat": 5, "lon": 5, "elev": 1, "slope_deg": 2, "aspect_sin": 3, "aspect_cos": 3, "tpi": 1})
    cells.to_csv(out, index=False)
    return cells
