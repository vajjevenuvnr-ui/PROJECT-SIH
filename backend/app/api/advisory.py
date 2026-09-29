from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import DS, OfficerDep, ensure_block, ensure_panchayat
from app.schemas.api import Advisory, AdvisoryGenerateRequest, AdvisoryPatch
from app.core.config import get_settings
from app.schemas.api import Lang
from app.services import advisory as engine
from app.services.forecast import panchayat_forecast
from app.services.messages import build_message, sms_info

router = APIRouter(prefix="/advisory", tags=["advisory"])


def _get(ds, advisory_id: int) -> dict:
    adv = ds.get_advisory(advisory_id)
    if adv is None:
        raise HTTPException(404, "Advisory not found")
    return adv


@router.get("/crops", summary="Crops and growth stages the rule engine supports (names in en/te/hi)")
def crops():
    return engine.crop_catalog()


@router.post("/generate", response_model=Advisory, summary="S4: generate a draft crop advisory")
def generate(body: AdvisoryGenerateRequest, ds: DS, officer: OfficerDep):
    """Runs the YAML rule engine on the panchayat's 5-day forecast for a crop and growth stage.
    Items are ranked by urgency, then Avoid > Prepare > Do now, carry text in en/te/hi, and an
    `explain` block with each condition's threshold and the actual forecast value."""
    ensure_panchayat(ds, officer, body.panchayat_id)
    engine.validate(body.crop, body.stage)
    fc = panchayat_forecast(ds, body.panchayat_id)
    items = engine.evaluate(fc["days"], body.crop, body.stage, fc["panchayat"]["confidence"])
    return ds.insert_advisory({
        "panchayat_id": body.panchayat_id, "run_id": fc["run"]["id"],
        "crop": body.crop, "stage": body.stage, "items": items, "status": "draft",
    })


class BulkGenerate(BaseModel):
    block_id: int
    panchayat_ids: list[int] | None = None


@router.post("/generate-bulk", summary="Draft advisories for many panchayats using their crop profiles")
def generate_bulk(body: BulkGenerate, ds: DS, officer: OfficerDep):
    """Crop and stage come from each panchayat's crop profile (sowing date -> stage), so the officer
    does not pick them one by one. Returns one draft per panchayat."""
    from datetime import date as date_cls

    from app.services.profiles import resolve

    ensure_block(officer, body.block_id)
    gps = ds.list_panchayats(body.block_id)
    if body.panchayat_ids:
        gps = [g for g in gps if g["id"] in set(body.panchayat_ids)]
    saved = ds.get_crop_profiles()
    out = []
    for g in gps:
        fc = panchayat_forecast(ds, g["id"])
        prof = resolve(saved.get(g["id"]), g["id"], date_cls.fromisoformat(fc["days"][0]["date"]))
        items = engine.evaluate(fc["days"], prof["crop"], prof["stage"], fc["panchayat"]["confidence"])
        adv = ds.insert_advisory({"panchayat_id": g["id"], "run_id": fc["run"]["id"], "crop": prof["crop"],
                                  "stage": prof["stage"], "items": items, "status": "draft"})
        out.append({"advisory": adv, "profile": prof, "panchayat": {k: g.get(k) for k in ("id", "name", "name_te", "name_hi")},
                    "confidence": fc["panchayat"]["confidence"], "warnings": len(fc.get("warnings", []))})
    return out


class BulkSend(BaseModel):
    advisory_ids: list[int]
    channel: Literal["sms", "whatsapp"] = "sms"
    language: Lang = "te"


@router.post("/send-bulk", summary="Approve and send many advisories at once (simulated delivery)")
def send_bulk(body: BulkSend, ds: DS, officer: OfficerDep):
    # Check every advisory first, so a mixed request sends nothing instead of half.
    for aid in body.advisory_ids:
        adv = ds.get_advisory(aid)
        if adv is not None:
            ensure_panchayat(ds, officer, adv["panchayat_id"])
    results, total = [], 0
    for aid in body.advisory_ids:
        adv = ds.get_advisory(aid)
        if adv is None:
            continue
        if adv["status"] == "draft":
            ds.update_advisory(aid, {"status": "approved", **({"approved_by": officer.id} if officer.id else {})})
        from app.api.farmers import recipients

        gp = ds.get_panchayat(adv["panchayat_id"]) or {}
        entry = ds.insert_share_log({"advisory_id": aid, "channel": body.channel, "language": body.language,
                                     "recipients": recipients(ds, gp), "status": "Delivered (simulated)"})
        ds.update_advisory(aid, {"status": "sent"})
        total += entry["recipients"]
        results.append(entry)
    return {"sent": len(results), "farmers": total, "log": results}


@router.get("/{advisory_id}", response_model=Advisory, summary="Get one advisory")
def get_advisory(advisory_id: int, ds: DS):
    return _get(ds, advisory_id)


@router.patch("/{advisory_id}", response_model=Advisory, summary="Officer edits advisory text")
def edit(advisory_id: int, body: AdvisoryPatch, ds: DS, officer: OfficerDep):
    adv = _get(ds, advisory_id)
    ensure_panchayat(ds, officer, adv["panchayat_id"])
    if adv["status"] == "sent":
        raise HTTPException(409, "Advisory already sent; generate a new one")
    patch = body.model_dump(exclude_none=True)
    return ds.update_advisory(advisory_id, patch) if patch else adv


@router.post("/{advisory_id}/approve", response_model=Advisory, summary="Approve advisory for sending")
def approve(advisory_id: int, ds: DS, officer: OfficerDep):
    adv = _get(ds, advisory_id)
    ensure_panchayat(ds, officer, adv["panchayat_id"])
    if adv["status"] == "sent":
        return adv
    patch = {"status": "approved"}
    if officer.id:
        patch["approved_by"] = officer.id
    return ds.update_advisory(advisory_id, patch)


@router.get("/{advisory_id}/message", summary="S5: farmer message text (SMS or WhatsApp) with SMS segment count")
def message(
    advisory_id: int,
    ds: DS,
    lang: Lang = "te",
    channel: Literal["sms", "whatsapp"] = "sms",
    base_url: str | None = Query(None, description="Public app address used in the link, e.g. http://192.168.1.5:3000"),
):
    """Builds the message a farmer receives. The link opens the no-login farmer page `/f/{panchayat_id}`.
    For SMS, `segments` counts parts (UCS-2 for Telugu/Hindi: 70 chars, 67 per part when split)."""
    adv = _get(ds, advisory_id)
    fc = panchayat_forecast(ds, adv["panchayat_id"])
    base = base_url if base_url and base_url.startswith(("http://", "https://")) else get_settings().public_app_url
    link = f"{base.rstrip('/')}/f/{adv['panchayat_id']}?lang={lang}"
    text = build_message(advisory=adv, forecast=fc, lang=lang, channel=channel, link=link)
    gp = fc["panchayat"]
    return {
        "advisory_id": advisory_id, "lang": lang, "channel": channel, "text": text, "link": link,
        "sms": sms_info(text),
        "panchayat": {"id": gp["id"], "name": gp["name"], "name_te": gp.get("name_te"), "name_hi": gp.get("name_hi"),
                      "registered_farmers": gp.get("registered_farmers") or 0},
    }
