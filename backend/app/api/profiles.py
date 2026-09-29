from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import DS, OfficerDep, ensure_panchayat
from app.services import advisory as engine
from app.services.forecast import require_run
from app.services.profiles import resolve

router = APIRouter(prefix="/crop-profiles", tags=["crop profiles"])


def _on(ds) -> date:
    """Stage is computed for Day 1 of the latest forecast."""
    run = require_run(ds)
    rows = ds.panchayat_forecasts(run["id"], [p["id"] for b in ds.list_blocks() for p in ds.list_panchayats(b["id"])][:1])
    return date.fromisoformat(min(r["date"] for r in rows)) if rows else date.today()


@router.get("", summary="Crop profile (crop, sowing date, derived stage) for every panchayat of a block")
def list_profiles(block_id: int, ds: DS):
    on = _on(ds)
    saved = ds.get_crop_profiles()
    return [resolve(saved.get(g["id"]), g["id"], on) | {"name": g["name"], "name_te": g.get("name_te"), "name_hi": g.get("name_hi")}
            for g in ds.list_panchayats(block_id)]


@router.get("/{panchayat_id}", summary="One panchayat's crop profile with its current growth stage")
def get_profile(panchayat_id: int, ds: DS):
    if ds.get_panchayat(panchayat_id) is None:
        raise HTTPException(404, "Panchayat not found")
    return resolve(ds.get_crop_profiles().get(panchayat_id), panchayat_id, _on(ds))


class ProfileIn(BaseModel):
    crop: str = Field(examples=["cotton"])
    sowing_date: date


@router.put("/{panchayat_id}", summary="Officer sets a panchayat's main crop and sowing date (once per season)")
def set_profile(panchayat_id: int, body: ProfileIn, ds: DS, officer: OfficerDep):
    ensure_panchayat(ds, officer, panchayat_id)
    if body.crop not in engine.load_rules()["crops"]:
        raise HTTPException(422, "Unknown crop")
    ds.set_crop_profile({"panchayat_id": panchayat_id, "crop": body.crop, "sowing_date": body.sowing_date.isoformat(),
                         "is_default": False})
    return resolve(ds.get_crop_profiles().get(panchayat_id), panchayat_id, _on(ds))
