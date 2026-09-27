import json

from fastapi import APIRouter, HTTPException

from app.api.deps import DS
from app.core.datasource import DEMO_DIR

router = APIRouter(prefix="/validation", tags=["validation"])

LOWER_IS_BETTER = {"rmse", "mae", "far"}
MODELS_META = DEMO_DIR.parents[0] / "models" / "meta.json"


def _improvement(base: float | None, ours: float | None) -> float | None:
    """Percent change of ours vs block baseline (negative = lower)."""
    if base in (None, 0) or ours is None:
        return None
    return round((ours - base) / abs(base) * 100, 1)


def _read(path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@router.get("", summary="S6: accuracy vs the 'copy block value' baseline at stations never used in training")
def validation(ds: DS, variable: str | None = None, period: str | None = None):
    """Metrics for both methods, % change (+ bootstrap 90% CI from the validation run), backtest events,
    per-station scores, a Tmax scatter sample, and the engine's model-to-model skill from training.
    `is_placeholder` is true for the synthetic seed - the UI labels those numbers as illustrative."""
    metrics = [m for m in ds.validation_metrics(variable) if period is None or m["period"] == period]
    grouped: dict[tuple, dict] = {}
    for m in metrics:
        key = (m["variable"], m.get("threshold_mm"), m["period"])
        g = grouped.setdefault(key, {"variable": m["variable"], "threshold_mm": m.get("threshold_mm"),
                                     "period": m["period"], "n_stations": m.get("n_stations"),
                                     "n_samples": m.get("n_samples"), "n_events": m.get("n_events")})
        g[m["method"]] = {k: m.get(k) for k in ("rmse", "bias", "mae", "pod", "far", "csi")}
    for g in grouped.values():
        base, ours = g.get("block_baseline", {}), g.get("panchayatcast", {})
        g["change_pct"] = {k: _improvement(base.get(k), ours.get(k))
                           for k in ("rmse", "mae", "pod", "far", "csi") if base.get(k) is not None}
    stations = {s["id"]: s for s in ds.list_stations()}
    events = [{**e, "station_name": e.get("station_name") or stations.get(e.get("station_id"), {}).get("name")}
              for e in ds.backtest_events()]
    summary = (_read(DEMO_DIR / "validation.json") or {}).get("summary")
    meta = _read(MODELS_META)
    return {
        "is_placeholder": any(m.get("is_placeholder") for m in metrics) or any(e.get("is_placeholder") for e in events),
        "method_note": (summary or {}).get("method_note") or (
            "Stations not used in training. Baseline = IMD block value copied to every panchayat. "
            "Rain scores follow IMD categorical verification (POD / FAR / CSI)."),
        "lower_is_better": sorted(LOWER_IS_BETTER),
        "metrics": list(grouped.values()),
        "backtest_events": events,
        "stations": [{k: v for k, v in s.items() if k != "geom"} for s in stations.values()],
        "summary": summary,
        "engine_skill": {"method": meta.get("method"), "trained_at": meta.get("trained_at"),
                         "holdout": meta.get("skill_holdout"), "training": meta.get("training")} if meta else None,
    }


@router.get("/station/{station_id}/series", summary="Daily observed vs block vs Kshetra at one station")
def station_series(station_id: str):
    series = _read(DEMO_DIR / "validation_series.json") or {}
    if station_id not in series:
        raise HTTPException(404, "No validation series for this station")
    return series[station_id]
