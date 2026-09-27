"""Per-panchayat crop profile: main crop + sowing date, stored once; the growth stage follows from the date.

Panchayats without a saved profile get an illustrative default (a cotton / paddy / maize mix sown
40-65 days before the forecast), marked is_default so the UI can say so.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.services.advisory import load_rules, stage_for

DEFAULT_CROPS = ["cotton", "paddy", "cotton", "maize", "cotton"]  # id 7 (Ahmadipur) -> cotton


def default_profile(panchayat_id: int, on: date) -> dict:
    crop = DEFAULT_CROPS[panchayat_id % len(DEFAULT_CROPS)]
    return {"panchayat_id": panchayat_id, "crop": crop,
            "sowing_date": (on - timedelta(days=40 + (panchayat_id * 7) % 26)).isoformat(), "is_default": True}


def resolve(profile: dict | None, panchayat_id: int, on: date) -> dict:
    p = dict(profile) if profile else default_profile(panchayat_id, on)
    p.setdefault("is_default", False)
    stage, days = stage_for(p["crop"], date.fromisoformat(p["sowing_date"]), on)
    names = load_rules()["stages"][stage]
    return {**p, "stage": stage, "stage_name": names, "days_since_sowing": days, "on": on.isoformat()}
