"""Lightweight, no-login payload for the farmer page (S7)."""

from fastapi import APIRouter

from app.api.deps import DS
from app.schemas.api import Lang
from app.services.forecast import panchayat_forecast
from app.services.messages import CONFIDENCE_WORDS

router = APIRouter(prefix="/public", tags=["public"])

@router.get("/panchayat/{panchayat_id}", summary="S7 farmer page data (public)")
def public_panchayat(panchayat_id: int, ds: DS, lang: Lang = "te"):
    fc = panchayat_forecast(ds, panchayat_id)
    gp = fc["panchayat"]
    name = gp.get(f"name_{lang}") if lang != "en" else None
    words = CONFIDENCE_WORDS[lang]
    days = [{k: d[k] for k in ("day", "date", "weekday", "rain_mm", "rain_prob_10mm", "rain_prob_2_5mm", "tmax",
                               "tmin", "rh", "wind_kmh", "confidence")}
            for d in fc["days"]]
    adv = ds.latest_advisory(panchayat_id, ("approved", "sent"))
    return {
        "panchayat": {"id": gp["id"], "name": name or gp["name"], "name_en": gp["name"],
                      "block": (gp["block"].get(f"name_{lang}") if lang != "en" else None) or gp["block"]["name"]},
        "lang": lang,
        "today": days[0],
        "days": days,
        "confidence": {"level": gp["confidence"],
                       "text": f"{words['label']}: {words[gp['confidence']]}"},
        "advisory": {"id": adv["id"], "crop": adv["crop"], "stage": adv["stage"], "items": adv["items"],
                     "edited_text": adv.get("edited_text")} if adv else None,
        "issued_at": fc["run"]["issued_at"],
        "source_label": fc["run"]["source_label"],
        "warnings": [
            {k: w[k] for k in ("id", "level", "hazard", "event", "day", "date", "value", "unit", "confidence",
                               "siren", "simulated")}
            | {"title": w["title"][lang], "body": w["body"][lang], "actions": w["actions"][lang]}
            for w in fc["warnings"]
        ],
    }
