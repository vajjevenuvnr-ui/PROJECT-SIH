from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from app.api.deps import DS
from app.schemas.api import RainFeedback

router = APIRouter(prefix="/feedback", tags=["feedback"])
IST = timezone(timedelta(hours=5, minutes=30))


@router.get("/summary", summary="Farmer rain reports per panchayat vs the forecast (crowdsourced check)")
def summary(ds: DS, block_id: int):
    """Groups "Did it rain today?" answers by panchayat and date and compares with the forecast rain
    for that date: agree when the majority answer matches forecast rain >= 2.5 mm."""
    from app.services.forecast import block_bundle

    _, run, gps, _, pfc = block_bundle(ds, block_id)
    fc = {(r["panchayat_id"], r["date"]): r for r in pfc}
    names = {g["id"]: g for g in gps}
    groups: dict[tuple, list[bool]] = {}
    for f in ds.list_feedback(list(names)):
        groups.setdefault((f["panchayat_id"], f["date"]), []).append(bool(f["rained"]))
    rows, agree, judged = [], 0, 0
    for (gid, d), votes in sorted(groups.items()):
        yes = sum(votes)
        r = fc.get((gid, d))
        forecast_wet = None if r is None else r["rain_mm"] >= 2.5
        majority_wet = yes * 2 > len(votes)
        match = None if forecast_wet is None or yes * 2 == len(votes) else forecast_wet == majority_wet
        if match is not None:
            judged += 1
            agree += int(match)
        g = names[gid]
        rows.append({"panchayat_id": gid, "panchayat": {k: g.get(k) for k in ("id", "name", "name_te", "name_hi")},
                     "date": d, "yes": yes, "no": len(votes) - yes,
                     "forecast_rain_mm": None if r is None else r["rain_mm"], "agree": match})
    return {"reports": sum(len(v) for v in groups.values()), "panchayats": len({k[0] for k in groups}),
            "agreement": round(agree / judged, 2) if judged else None, "judged": judged, "rows": rows}


@router.post("/rain", status_code=201, summary='S7: farmer "Did it rain today?" (no login)')
def rain_feedback(body: RainFeedback, ds: DS):
    if ds.get_panchayat(body.panchayat_id) is None:
        raise HTTPException(404, "Panchayat not found")
    rec = ds.insert_feedback({"panchayat_id": body.panchayat_id, "rained": body.rained,
                              "date": datetime.now(IST).date().isoformat()})
    return {"ok": True, "id": rec.get("id")}
