from fastapi import APIRouter, HTTPException

from app.api.deps import DS, OfficerDep
from app.api.farmers import recipients
from app.schemas.api import ShareLogEntry, ShareRequest

router = APIRouter(prefix="/share", tags=["share"])

SIMULATED_STATUS = "Delivered (simulated)"


@router.post("", response_model=ShareLogEntry, summary="S5: send an approved advisory (simulated)")
def share(body: ShareRequest, ds: DS, officer: OfficerDep):
    """No real SMS/WhatsApp gateway (out of scope). Records the send in the log and returns
    the recipient count = the panchayat's farmer contacts (or registered farmers if none uploaded)."""
    adv = ds.get_advisory(body.advisory_id)
    if adv is None:
        raise HTTPException(404, "Advisory not found")
    if adv["status"] == "draft":
        raise HTTPException(409, "Approve the advisory before sending")
    gp = ds.get_panchayat(adv["panchayat_id"])
    entry = ds.insert_share_log({
        "advisory_id": body.advisory_id, "channel": body.channel, "language": body.language,
        "recipients": recipients(ds, gp), "status": SIMULATED_STATUS,
    })
    ds.update_advisory(body.advisory_id, {"status": "sent"})
    return entry


@router.get("/log", response_model=list[ShareLogEntry], summary="Send history (newest first)")
def share_log(ds: DS, advisory_id: int | None = None):
    return ds.list_share_log(advisory_id)
