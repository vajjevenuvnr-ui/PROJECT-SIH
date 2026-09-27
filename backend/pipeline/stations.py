"""Ground-truth station observations for validation (stations are never used in training).

Sources, in order:
  1. State AWS CSVs you drop into data/stations/aws/*.csv (e.g. Telangana TGDPS). Columns:
     station_id, name, lat, lon, [elev], date (YYYY-MM-DD), rain_mm, tmax, tmin
  2. NOAA GSOD daily summaries of IMD synoptic stations (downloaded automatically).

Quality control (Data Strategy 5.1): range and consistency checks; qc_flag 0 = raw, 2 = removed.
GSOD precipitation flagged I (no report) or H (reported 0 while rain occurred) is treated as missing.
GSOD days are UTC days; the validation uses UTC daily forecasts to match.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import httpx
import pandas as pd

from pipeline.common import BACKEND

DIR = BACKEND / "data" / "stations"
ISD = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
GSOD = "https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/{year}/{sid}.csv"


def _km(a_lat, a_lon, b_lat, b_lon) -> float:
    p = math.radians
    h = math.sin(p(b_lat - a_lat) / 2) ** 2 + math.cos(p(a_lat)) * math.cos(p(b_lat)) * math.sin(p(b_lon - a_lon) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _download(url: str, path: Path) -> bool:
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")[:20].startswith('"STATION"')
    try:
        r = httpx.get(url, timeout=90)
    except httpx.HTTPError:
        return False
    if r.status_code != 200 or not r.text.startswith('"STATION"'):
        return False
    path.write_text(r.text, encoding="utf-8")
    return True


def gsod_stations_near(lat: float, lon: float, radius_km: float, since: str) -> list[dict]:
    DIR.mkdir(parents=True, exist_ok=True)
    isd = DIR / "isd-history.csv"
    if not isd.exists():
        isd.write_bytes(httpx.get(ISD, timeout=120).content)
    out = []
    with open(isd, encoding="utf-8", errors="ignore") as fh:
        for r in csv.DictReader(fh):
            try:
                la, lo = float(r["LAT"]), float(r["LON"])
            except ValueError:
                continue
            if r["CTRY"] == "IN" and r["END"] >= since and _km(lat, lon, la, lo) <= radius_km:
                out.append({"sid": r["USAF"] + r["WBAN"], "name": r["STATION NAME"].title(), "lat": la, "lon": lo,
                            "elev": float(r["ELEV(M)"]) if r["ELEV(M)"] else None, "distance_km": round(_km(lat, lon, la, lo))})
    return sorted(out, key=lambda s: s["distance_km"])


def load_gsod(stations: list[dict], years: list[int]) -> pd.DataFrame:
    frames = []
    for s in stations:
        for y in years:
            path = DIR / f"gsod-{y}-{s['sid']}.csv"
            if not _download(GSOD.format(year=y, sid=s["sid"]), path):
                continue
            d = pd.read_csv(path)
            prcp_flag = d["PRCP_ATTRIBUTES"].astype(str).str.strip()
            frames.append(pd.DataFrame({
                "station_id": s["sid"], "name": s["name"], "lat": s["lat"], "lon": s["lon"], "elev": s["elev"],
                "distance_km": s["distance_km"], "source": "NOAA GSOD (IMD synoptic station)",
                "date": pd.to_datetime(d["DATE"]).dt.strftime("%Y-%m-%d"),
                "tmax": ((d["MAX"] - 32) * 5 / 9).where(d["MAX"] < 999),
                "tmin": ((d["MIN"] - 32) * 5 / 9).where(d["MIN"] < 999),
                "rain_mm": (d["PRCP"] * 25.4).where((d["PRCP"] < 99) & ~prcp_flag.isin(["I", "H"])),
            }))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_state_aws() -> pd.DataFrame:
    files = sorted((DIR / "aws").glob("*.csv")) if (DIR / "aws").exists() else []
    if not files:
        return pd.DataFrame()
    d = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    d["source"] = "State AWS network"
    d["distance_km"] = None
    if "elev" not in d:
        d["elev"] = None
    return d[["station_id", "name", "lat", "lon", "elev", "distance_km", "source", "date", "tmax", "tmin", "rain_mm"]]


IMD_DIR = BACKEND / "data" / "raw" / "imd"


def load_imd_grid(lat: float, lon: float, radius_km: float, years: list[int]) -> pd.DataFrame:
    """IMD 0.25 deg gridded daily rainfall (Pai et al. 2014; built from IMD's rain-gauge network), downloaded with
    imdlib into data/raw/imd/rain/<year>.grd. Each grid cell near the block becomes a rain-only "station".
    IMD day = 08:30 IST to 08:30 IST next day. Values are 25 km area means, not point gauges."""
    files = [IMD_DIR / "rain" / f"{y}.grd" for y in years]
    if not all(f.exists() for f in files):
        return pd.DataFrame()
    import imdlib

    da = imdlib.open_data("rain", min(years), max(years), "yearwise", str(IMD_DIR)).get_xarray()["rain"]
    rows = []
    for la in da.lat.values:
        for lo in da.lon.values:
            dist = _km(lat, lon, float(la), float(lo))
            if dist > radius_km:
                continue
            ser = da.sel(lat=la, lon=lo).to_series()
            ser = ser[ser > -99]
            if ser.empty:
                continue
            sid = f"IMD-{float(la):.2f}N-{float(lo):.2f}E"
            for t, v in ser.items():
                rows.append({"station_id": sid, "name": f"IMD grid {float(la):.2f}N {float(lo):.2f}E",
                             "lat": float(la), "lon": float(lo), "elev": None, "distance_km": round(dist, 0),
                             "source": "IMD gridded rainfall 0.25° (gauge-based)", "date": t.strftime("%Y-%m-%d"),
                             "tmax": float("nan"), "tmin": float("nan"), "rain_mm": float(v)})
    return pd.DataFrame(rows)


def qc(df: pd.DataFrame) -> pd.DataFrame:
    """Range + consistency checks. Bad values become NaN; qc_flag = 2 if anything was removed."""
    df = df.copy()
    bad_t = (df["tmax"] < -5) | (df["tmax"] > 50) | (df["tmin"] < -10) | (df["tmin"] > 40) | (df["tmax"] <= df["tmin"])
    bad_r = (df["rain_mm"] < 0) | (df["rain_mm"] > 500)
    df.loc[bad_t, ["tmax", "tmin"]] = float("nan")
    df.loc[bad_r, "rain_mm"] = float("nan")
    df["qc_flag"] = (bad_t | bad_r).astype(int) * 2
    return df


def observations(lat: float, lon: float, radius_km: float, years: list[int], months: list[int]) -> pd.DataFrame:
    since = f"{min(years)}0101"
    gs = load_gsod(gsod_stations_near(lat, lon, radius_km, since), years)
    imd = load_imd_grid(lat, lon, 40, years)
    df = pd.concat([x for x in (load_state_aws(), imd, gs) if len(x)], ignore_index=True)
    df = qc(df)
    df = df[pd.to_datetime(df["date"]).dt.month.isin(months)]
    usable = df.groupby("station_id")[["tmax", "rain_mm"]].count()
    keep = usable[(usable["tmax"] >= 30) | (usable["rain_mm"] >= 30)].index
    return df[df["station_id"].isin(keep)].reset_index(drop=True)
