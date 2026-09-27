"""Change-based officer notifications: compare the current run with the previous one, per panchayat and date,
and report only what matters (the officer need not re-check every forecast).

Reported when, for the same panchayat and date:
  * rain changes by >= RAIN_JUMP_MM            ("Ahmadipur: rain 5 -> 40 mm, Tue")
  * the IMD rain category changes, reaching moderate or heavier
  * confidence drops to Low
  * a new or upgraded Orange / Red warning appears
"""

from __future__ import annotations

from datetime import date as date_cls

from app.core.imd import rain_category
from app.services.advisory import WEEKDAYS
from app.services.warnings import RANK, warnings_for_day

RAIN_JUMP_MM = 15.0
HEAVIER = {"moderate", "heavy", "very_heavy", "extremely_heavy"}
LANGS = ("en", "te", "hi")
TEXT = {
    "rain": {"en": "{gp}: rain {a} → {b} mm, {day}", "te": "{gp}: వర్షం {a} → {b} మి.మీ., {day}",
             "hi": "{gp}: वर्षा {a} → {b} मि.मी., {day}"},
    "confidence": {"en": "{gp}: forecast confidence dropped to Low, {day}", "te": "{gp}: అంచనా నమ్మకం తక్కువకు పడిపోయింది, {day}",
                   "hi": "{gp}: पूर्वानुमान विश्वसनीयता कम हुई, {day}"},
    "alert": {"en": "{gp}: new {title}, {day}", "te": "{gp}: కొత్త {title}, {day}", "hi": "{gp}: नया {title}, {day}"},
}


def _num(v: float) -> str:
    r = round(float(v), 1)
    return str(int(r)) if r == int(r) else str(r)


def compute_changes(prev_rows: list[dict], cur_rows: list[dict], gps: dict[int, dict], run: dict, prev_run: dict) -> list[dict]:
    prev = {(r["panchayat_id"], r["date"]): r for r in prev_rows}
    out = []
    for r in cur_rows:
        p = prev.get((r["panchayat_id"], r["date"]))
        gp = gps.get(r["panchayat_id"])
        if p is None or gp is None:
            continue
        names = {lang: (gp.get(f"name_{lang}") if lang != "en" else None) or gp["name"] for lang in LANGS}
        wd = {lang: WEEKDAYS[lang][date_cls.fromisoformat(r["date"]).weekday()] for lang in LANGS}
        base = {"panchayat_id": gp["id"], "panchayat": {k: gp.get(k) for k in ("id", "name", "name_te", "name_hi")},
                "date": r["date"], "day": r["day"]}

        a, b = p["rain_mm"], r["rain_mm"]
        cat_a, cat_b = rain_category(a)["key"], rain_category(b)["key"]
        if abs(b - a) >= RAIN_JUMP_MM or (cat_a != cat_b and cat_b in HEAVIER):
            out.append({**base, "kind": "rain", "severity": "high" if b - a >= 30 else "medium",
                        "from": a, "to": b, "category_from": cat_a, "category_to": cat_b,
                        "text": {lang: TEXT["rain"][lang].format(gp=names[lang], a=_num(a), b=_num(b), day=wd[lang]) for lang in LANGS}})
        if r["confidence"] == "low" and p["confidence"] != "low":
            out.append({**base, "kind": "confidence", "severity": "low", "from": p["confidence"], "to": "low",
                        "text": {lang: TEXT["confidence"][lang].format(gp=names[lang], day=wd[lang]) for lang in LANGS}})
        old = {w["hazard"]: w["level"] for w in warnings_for_day(p, gp, prev_run)}
        for w in warnings_for_day(r, gp, run):
            if RANK[w["level"]] >= RANK["orange"] and (w["hazard"] not in old or RANK[w["level"]] > RANK[old[w["hazard"]]]):
                out.append({**base, "kind": "alert", "severity": "high", "from": old.get(w["hazard"]), "to": w["level"],
                            "alert_id": w["id"],
                            "text": {lang: TEXT["alert"][lang].format(gp=names[lang], title=w["title"][lang], day=wd[lang])
                                     for lang in LANGS}})
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda c: (order[c["severity"]], c["date"], -abs((c.get("to") or 0) if c["kind"] == "rain" else 0)))
