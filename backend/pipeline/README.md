# Kshetra downscaling pipeline

Block forecast → 1 km cells → gram panchayat values, consistent with the block value, with confidence.

## Commands (from `backend/`)

| Step | Command | When |
|---|---|---|
| Train models | `.venv/Scripts/python -m pipeline.train` | Once (downloads ~3 monsoon seasons, then cached) |
| Find a replay event | `.venv/Scripts/python -m pipeline.find_replay` | Once, to pick the demo day |
| Replay a past event (Demo Mode) | `.venv/Scripts/python -m pipeline.run_daily --replay YYYY-MM-DD --publish-demo` | For the demo |
| Live forecast | `.venv/Scripts/python -m pipeline.run_daily` | Daily (06:00 IST scheduler: `PIPELINE_SCHEDULE=true`) |
| Validate against stations (Phase 8) | `.venv/Scripts/python -m pipeline.validate` | After training; re-run when new station data arrives |
| Back to the synthetic seed | `.venv/Scripts/python -m scripts.seed_demo` | Any time |

Officers can also trigger a run from the API: `POST /api/admin/run-pipeline`, status at `GET /api/admin/pipeline-status`.

## Data actually used

All from **Open-Meteo** (free, no key, non-commercial use), cached in `data/cache/openmeteo/`:

| Role | Source | Resolution |
|---|---|---|
| Block forecast ("IMD-format demo feed") | Open-Meteo `best_match`, mean of model points inside the block | model-dependent |
| Ensemble for confidence | ECMWF IFS 0.25°, GFS, ICON | 0.25° / 0.25° / ~13 km |
| Replay of a past event | Open-Meteo Historical Forecast API (archived model runs) | as above |
| Coarse training field | ERA5 | 0.25° (~28 km) |
| Fine training target, temperature | ERA5-Land | 0.1° (~9 km) |
| Fine training target, rain | ECMWF IFS analysis archive | ~9 km |
| Terrain | Copernicus DEM (Open-Meteo elevation API) | 90 m, sampled on the 1 km grid |

## Method

- **Temperature:** `T = T_coarse + 6.5 °C/km × dz + XGBoost residual` (dz = block mean elevation − cell elevation).
- **Rain:** XGBoost classifiers for P(≥2.5 mm) and P(≥10 mm), an amount regressor on wet days, quantile
  mapping to the fine-scale distribution; expected rain = P(wet) × amount.
- **RH:** from downscaled temperature at constant vapour pressure. **Wind:** terrain exposure (TPI).
- **Mass consistency:** panchayat values are rescaled so their mean equals the block value
  (additive for temperature, multiplicative for rain and wind). We build on the official forecast, never replace it.
- **Confidence:** spread between ECMWF / GFS / ICON after downscaling, plus lead time → High / Medium / Low.

## Honest limitations (say these before judges ask)

- Training targets are ~9 km, so the 1 km detail comes from terrain physics (lapse rate, exposure) plus the
  learned 9 km patterns. CHIRPS 0.05° rain and ESRI 10 m land use / NDVI / distance-to-water are the planned upgrades.
- Trained on the monsoon season (June–October, 2021–2023) to stay within Open-Meteo's free limits.
- Skill printed by `pipeline.train` is **model-to-model** (held-out 9 km cells).
- Station validation (`pipeline.validate`, Jun-Sep 2024 + Jun-Aug 2025, 4 IMD synoptic stations via NOAA GSOD, 825
  station-days): Tmax/Tmin RMSE no clear difference vs the block value; rain CSI >=2.5 mm +3.4% (90% CI 0.2 to 6.7);
  >=10 mm +1.9% (CI -3.2 to 6.8). Stations are 50-130 km from Gajwel. Drop TGDPS AWS CSVs into
  `data/stations/aws/` (station_id,name,lat,lon,date,rain_mm,tmax,tmin) and re-run for denser, closer stations.
- Panchayat boundaries are still illustrative Voronoi cells; swap in the real Bhuvan / state GIS layer.
- The live feed is Open-Meteo, not IMD: labelled "Source: Open-Meteo (IMD-format demo feed)". `ingest_imd()` has
  the same output schema for the production switch.
