"""Extreme-weather alerts (Phase 6b): list, acknowledge, dispatch to farmers, CAP export, demo simulation, push."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import DS, OfficerDep
from app.core.datasource import use_demo
from app.services.cap import build_cap
from app.services.forecast import require_run
from app.services.push import push_enabled, send_push
from app.services.warnings import block_warnings, warnings_for_day

router = APIRouter(tags=["alerts"])

SIMULATED_SMS = "Delivered (simulated)"
SIMULATED_VOICE = "Called (simulated IVR)"


def find_alert(ds, alert_id: str) -> dict:
    """Recompute the warning an id refers to (ids are '<run>.<rev>-<gp>-<day>-<hazard>')."""
    try:
        _, gp_id, day, _ = alert_id.split("-", 3)
        gp_id, day = int(gp_id), int(day)
    except ValueError:
        raise HTTPException(404, "Unknown alert id") from None
    gp = ds.get_panchayat(gp_id)
    if gp is None:
        raise HTTPException(404, "Unknown alert id")
    run = require_run(ds)
    for row in ds.panchayat_forecasts(run["id"], [gp_id]):
        if row["day"] == day:
            for w in warnings_for_day(row, gp, run):
                if w["id"] == alert_id:
                    return w
    raise HTTPException(404, "This alert is no longer active (forecast changed)")


# ---------------------------------------------------------------- alerts
@router.get("/alerts", summary="IMD colour-coded warnings for a block (most severe first)")
def list_alerts(ds: DS, block_id: int, min_level: Literal["yellow", "orange", "red"] = "yellow"):
    """`siren` is true only for Orange/Red with High or Medium confidence."""
    warnings, run = block_warnings(ds, block_id, min_level)
    acks = ds.list_alert_acks()
    return {
        "alerts": warnings,
        "acknowledged": {k: v for k, v in acks.items() if any(w["id"] == k for w in warnings)},
        "simulation": ds.simulation_state(),
        "run": {"id": run["id"], "source": run["source"], "revision": run.get("revision", 0)},
        "push_enabled": push_enabled(),
    }


@router.get("/alerts/changes", summary="What changed since the previous forecast run (officer notifications)")
def changes(ds: DS, block_id: int):
    from app.services.changes import compute_changes
    from app.services.forecast import block_bundle

    _, run, gps, _, pfc = block_bundle(ds, block_id)
    prev_run, prev_rows = ds.previous_forecast([g["id"] for g in gps])
    if prev_run is None:
        return {"compared_with": None, "changes": []}
    label = "before the simulated event" if run.get("source") == "simulated" else f"run issued {prev_run['issued_at']}"
    return {"compared_with": label, "previous_run_id": prev_run["id"],
            "changes": compute_changes(prev_rows, pfc, {g["id"]: g for g in gps}, run, prev_run)}


@router.get("/alerts/log", summary="Alert dispatch history (push / SMS / voice)")
def alert_log(ds: DS, alert_id: str | None = None):
    return ds.list_alert_dispatch(alert_id)


@router.post("/alerts/{alert_id}/ack", summary="Officer acknowledges an alert (stops the siren)")
def acknowledge(alert_id: str, ds: DS, officer: OfficerDep):
    find_alert(ds, alert_id)
    return ds.ack_alert(alert_id, officer.name)


@router.post("/alerts/{alert_id}/dispatch", summary="Send the alert to the panchayat's farmers")
def dispatch(alert_id: str, ds: DS, officer: OfficerDep):
    """Web Push to subscribed phones (real, if VAPID keys are set) plus SMS and voice calls to all
    registered farmers (simulated - no real gateway in this prototype)."""
    w = find_alert(ds, alert_id)
    gp = w["panchayat"]
    subs = ds.list_push_subscriptions([gp["id"]])

    def payload(sub):
        lang = sub.get("lang", "te")
        return {"title": w["title"][lang], "body": w["body"][lang], "tag": w["id"], "lang": lang,
                "level": w["level"], "url": f"/f/{gp['id']}?lang={lang}&sos=1"}

    res = send_push(subs, payload)
    for endpoint in res["expired"]:
        ds.delete_push_subscription(endpoint)
    push_status = ("Push disabled (no VAPID keys)" if not push_enabled()
                   else f"Sent {res['sent']}, failed {res['failed']}" if subs else "No subscribed phones")
    rows = [
        ds.insert_alert_dispatch({"alert_id": alert_id, "panchayat_id": gp["id"], "channel": "push", "language": None,
                                  "recipients": len(subs), "delivered": res["sent"], "status": push_status}),
        ds.insert_alert_dispatch({"alert_id": alert_id, "panchayat_id": gp["id"], "channel": "sms_alert",
                                  "language": "te", "recipients": gp["registered_farmers"],
                                  "delivered": gp["registered_farmers"], "status": SIMULATED_SMS}),
        ds.insert_alert_dispatch({"alert_id": alert_id, "panchayat_id": gp["id"], "channel": "voice_alert",
                                  "language": "te", "recipients": gp["registered_farmers"],
                                  "delivered": gp["registered_farmers"], "status": SIMULATED_VOICE}),
    ]
    return {"alert_id": alert_id, "push": {"subscribers": len(subs), **res}, "log": rows}


@router.get("/alerts/{alert_id}/cap", summary="CAP 1.2 XML (NDMA SACHET format)")
def cap_xml(alert_id: str, ds: DS):
    w = find_alert(ds, alert_id)
    gp = ds.get_panchayat(w["panchayat_id"])
    block = ds.get_block(gp["block_id"])
    district = ds.get_district(block["district_id"]) if block else None
    state = next((s for s in ds.list_states() if district and s["id"] == district["state_id"]), None)
    xml = build_cap(w, require_run(ds), gp, block, district, state["name"] if state else "")
    return Response(xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="cap-{alert_id}.xml"'})


# ---------------------------------------------------------------- demo simulation
class SimulateRequest(BaseModel):
    panchayat_id: int | None = Field(None, description="Centre of the rain cell (default: the demo GP Ahmadipur)")
    day: int = Field(2, ge=1, le=5)


def _require_demo(request: Request):
    if not use_demo(request):
        raise HTTPException(409, "Simulation is only available in Demo Mode")


@router.post("/demo/simulate-extreme", summary="Demo Mode: create a clearly labelled very heavy rain event")
def simulate(body: SimulateRequest, request: Request, ds: DS, officer: OfficerDep):
    _require_demo(request)
    gp_id = body.panchayat_id
    if gp_id is None:
        gps = [g for b in ds.list_blocks() for g in ds.list_panchayats(b["id"])]
        gp_id = next((g["id"] for g in gps if g["name"] == "Ahmadipur"), gps[0]["id"] if gps else None)
    if gp_id is None or ds.get_panchayat(gp_id) is None:
        raise HTTPException(404, "Panchayat not found")
    return ds.simulate_extreme(gp_id, body.day)


@router.post("/demo/reset-simulation", summary="Demo Mode: remove the simulated event")
def reset(request: Request, ds: DS, officer: OfficerDep):
    _require_demo(request)
    ds.reset_simulation()
    return {"active": False}


# ---------------------------------------------------------------- web push (farmers, no login)
class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    endpoint: str
    keys: PushKeys


class SubscribeRequest(BaseModel):
    panchayat_id: int
    lang: Literal["te", "hi", "en"] = "te"
    subscription: PushSubscription


@router.get("/push/public-key", summary="VAPID public key for the farmer page")
def public_key():
    from app.core.config import get_settings

    return {"enabled": push_enabled(), "key": get_settings().vapid_public_key or None}


@router.post("/push/subscribe", status_code=201, summary="Farmer phone opts in to alerts for a panchayat")
def subscribe(body: SubscribeRequest, ds: DS):
    if not body.subscription.endpoint.startswith("https://"):
        raise HTTPException(422, "Invalid push endpoint")
    if ds.get_panchayat(body.panchayat_id) is None:
        raise HTTPException(404, "Panchayat not found")
    ds.upsert_push_subscription({"endpoint": body.subscription.endpoint, "p256dh": body.subscription.keys.p256dh,
                                 "auth": body.subscription.keys.auth, "panchayat_id": body.panchayat_id,
                                 "lang": body.lang})
    return {"ok": True}


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.post("/push/unsubscribe", summary="Remove a phone's alert subscription")
def unsubscribe(body: UnsubscribeRequest, ds: DS):
    ds.delete_push_subscription(body.endpoint)
    return {"ok": True}

