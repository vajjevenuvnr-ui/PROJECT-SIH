"""Rule-based agromet advisory engine (explainable).

Rules live in app/rules/crops.yaml. Each advisory item carries its text in en/te/hi and an
`explain` block: the rule, every condition (threshold vs actual value) and the forecast days used,
so the UI can answer "Why this advice?".
"""

from __future__ import annotations

import operator
from datetime import date as date_cls
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException

LANGS = ("en", "te", "hi")
RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "crops.yaml"
MODELS_META = Path(__file__).resolve().parents[2] / "data" / "models" / "meta.json"

OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}
TAG_ORDER = {"avoid": 0, "prepare": 1, "do_now": 2}

WEEKDAYS = {  # Monday first (date.weekday())
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "te": ["సోమవారం", "మంగళవారం", "బుధవారం", "గురువారం", "శుక్రవారం", "శనివారం", "ఆదివారం"],
    "hi": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
}

WET_MM = 2.5  # IMD "light rain" threshold
WET_P10 = 0.3


@lru_cache
def load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))


def crop_catalog() -> list[dict]:
    r = load_rules()
    return [
        {"id": cid, "name": c["name"], "icon": c.get("icon", cid),
         "stages": [{"id": s, "name": r["stages"][s]} for s in c["stages"]]}
        for cid, c in r["crops"].items()
    ]


def stage_for(crop: str, sowing: date_cls, on: date_cls) -> tuple[str, int]:
    """Growth stage from the crop calendar and days since sowing."""
    cal = load_rules()["crops"][crop]["calendar"]
    days = (on - sowing).days
    stage = cal and min(cal, key=lambda s: cal[s])
    for s, start in sorted(cal.items(), key=lambda kv: kv[1]):
        if days >= start:
            stage = s
    return stage, days


@lru_cache
def false_onset_climatology() -> dict[int, float]:
    """P(10-day dry spell within 30 days after a >=20 mm 2-day rain), by month, from training data."""
    import json

    try:
        meta = json.loads(MODELS_META.read_text(encoding="utf-8"))
        return {int(m): v["p"] for m, v in meta.get("false_onset", {}).items() if v.get("events", 0) >= 5}
    except (OSError, ValueError):
        return {}


def validate(crop: str, stage: str) -> None:
    crops = load_rules()["crops"]
    if crop not in crops:
        raise HTTPException(422, f"Unknown crop '{crop}'. Use one of: {', '.join(crops)}")
    if stage not in crops[crop]["stages"]:
        raise HTTPException(422, f"Unknown stage '{stage}' for {crop}. Use one of: {', '.join(crops[crop]['stages'])}")


def _num(v: float) -> str:
    """38.0 -> '38', 12.34 -> '12.3'."""
    r = round(float(v), 1)
    return str(int(r)) if r == int(r) else str(r)


def _weekday(iso: str, lang: str) -> str:
    return WEEKDAYS[lang][date_cls.fromisoformat(iso).weekday()]


def compute_metrics(days: list[dict]) -> dict[str, Any]:
    """Metrics over the panchayat's Days 1-5 (rows from the panchayat forecast response)."""
    d = sorted(days, key=lambda x: x["day"])
    first2, first3 = d[:2], d[:3]
    rain = lambda x: x.get("rain_mm") or 0.0  # noqa: E731
    wettest = max(first3, key=rain)

    # First dry day after the first wet spell (used for "until {day}").
    def wet(x):
        return rain(x) >= WET_MM or (x.get("rain_prob_10mm") or 0) >= WET_P10

    until = d[0]
    start = next((i for i, x in enumerate(d) if wet(x)), None)
    if start is not None:
        i = start
        while i < len(d) and wet(d[i]):
            i += 1
        until = d[min(i, len(d) - 1)]

    return {
        "p10_48h": max((x.get("rain_prob_10mm") or 0) for x in first2),
        "p25_48h": max((x.get("rain_prob_2_5mm") or 0) for x in first2),
        "rain_today": rain(d[0]),
        "rain_48h": round(sum(rain(x) for x in first2), 1),
        "rain_max_3d": rain(wettest),
        "rain_5d": round(sum(rain(x) for x in d), 1),
        "wind_today": d[0].get("wind_kmh") or 0.0,
        "wind_max_5d": max((x.get("wind_kmh") or 0) for x in d),
        "tmax_max_5d": max(x["tmax"] for x in d),
        "rh_max_3d": max((x.get("rh") or 0) for x in first3),
        "false_onset_p": false_onset_climatology().get(date_cls.fromisoformat(d[0]["date"]).month, 0.0),
        "_wettest": wettest,
        "_until": until,
    }


def _placeholders(m: dict, lang: str, crop_name: str) -> dict[str, str]:
    return {
        "prob": _num(m["p10_48h"] * 100), "prob25": _num(m["p25_48h"] * 100),
        "mm": _num(m["rain_max_3d"]), "day": _weekday(m["_wettest"]["date"], lang),
        "until": _weekday(m["_until"]["date"], lang), "rain5": _num(m["rain_5d"]),
        "rain48": _num(m["rain_48h"]), "rain_today": _num(m["rain_today"]),
        "tmax": _num(m["tmax_max_5d"]), "wind_today": _num(m["wind_today"]),
        "wind_max": _num(m["wind_max_5d"]), "rh": _num(m["rh_max_3d"]), "crop": crop_name,
        "fop": _num(m["false_onset_p"] * 100),
    }


def _applies(rule: dict, crop: str, stage: str) -> bool:
    crops = rule.get("crops", "all")
    if crops == "all":
        return stage not in rule.get("exclude_stages", [])
    if isinstance(crops, list):
        return crop in crops and stage not in rule.get("exclude_stages", [])
    return stage in crops.get(crop, [])  # {crop: [stages]}


def _explain(rule_id: str, conds: list, m: dict, days: list[dict], window: list[int]) -> dict:
    metrics = load_rules()["metrics"]
    out = []
    for name, op, threshold in conds:
        meta = metrics[name]
        scale = meta.get("scale", 1)
        out.append({
            "metric": name, "label": meta["label"], "op": op, "unit": meta["unit"],
            "threshold": round(threshold * scale, 1), "actual": round(m[name] * scale, 1),
        })
    used = [
        {k: x.get(k) for k in ("day", "date", "weekday", "rain_mm", "rain_prob_10mm", "tmax", "rh", "wind_kmh")}
        for x in sorted(days, key=lambda x: x["day"]) if x["day"] in window
    ]
    return {"rule_id": rule_id, "conditions": out, "days_used": used}


def evaluate(days: list[dict], crop: str, stage: str, confidence: str) -> list[dict]:
    """Ranked advisory items for one panchayat forecast (Days 1-5)."""
    validate(crop, stage)
    r = load_rules()
    m = compute_metrics(days)
    crop_names = r["crops"][crop]["name"]
    fill = {lang: _placeholders(m, lang, crop_names[lang]) for lang in LANGS}
    by_day = {x["day"]: x for x in days}

    items = []
    for rule in r["rules"]:
        if not _applies(rule, crop, stage):
            continue
        conds = rule["when"]
        if not all(OPS[op](m[name], threshold) for name, op, threshold in conds):
            continue
        window = rule.get("days", [1, 2, 3, 4, 5])
        items.append({
            "id": rule["id"],
            "tag": rule["tag"],
            "urgency": rule["urgency"],
            "valid_days": [{"day": d, "date": by_day[d]["date"]} for d in window if d in by_day],
            "title": {lang: rule["title"][lang].format(**fill[lang]) for lang in LANGS},
            "reason": {lang: rule["reason"][lang].format(**fill[lang]) for lang in LANGS},
            "explain": _explain(rule["id"], conds, m, days, window),
        })

    if confidence == "low":
        lc = r["low_confidence"]
        items.append({
            "id": "low_confidence", "tag": lc["tag"], "urgency": lc["urgency"],
            "valid_days": [{"day": x["day"], "date": x["date"]} for x in days[:3]],
            "title": dict(lc["title"]), "reason": dict(lc["reason"]),
            "explain": {"rule_id": "low_confidence", "conditions": [], "days_used": [],
                        "note": "Confidence is Low for Days 1-3 (large spread between models)."},
        })

    # Most time-critical first; within the same urgency: Avoid > Prepare > Do now.
    items.sort(key=lambda it: (it["urgency"], TAG_ORDER[it["tag"]]))
    return items
