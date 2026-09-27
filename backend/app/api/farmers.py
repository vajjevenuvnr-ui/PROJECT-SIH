"""Farmer contacts: officer CSV / Excel upload, masked listing, and farmer self-registration with consent.

Phone numbers are personal data. The API never returns a full number: officers see 98xxxxxx21.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import DS, OfficerDep
from app.services import advisory as engine

router = APIRouter(prefix="/farmers", tags=["farmers"])

MAX_ROWS = 5000
LANGS = {"te": "te", "telugu": "te", "తెలుగు": "te", "hi": "hi", "hindi": "hi", "हिंदी": "hi", "en": "en", "english": "en"}
TEMPLATE = ("name,mobile,panchayat,crop,language\n"
            "Ramesh,9876543210,Ahmadipur,cotton,te\n"
            "Sita Devi,+91 91234 56789,Akaram,paddy,te\n")


def normalize_mobile(raw) -> str | None:
    """Indian mobile: 10 digits starting 6-9, optional +91 / 91 / 0 prefix, spaces or dashes."""
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw).split(".")[0] if isinstance(raw, float) else str(raw))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if re.fullmatch(r"[6-9]\d{9}", digits) else None


def mask(mobile: str) -> str:
    return f"{mobile[:2]}xxxxxx{mobile[-2:]}"


def recipients(ds, gp: dict | None) -> int:
    """Who an advisory goes to: the panchayat's farmer contacts if any were uploaded / registered,
    otherwise the registered-farmer count on record (estimate)."""
    if not gp:
        return 0
    n = sum(1 for f in ds.list_farmers([gp["id"]]) if f.get("active", True))
    return n or (gp.get("registered_farmers") or 0)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_rows(file: UploadFile, data: bytes) -> list[dict]:
    name = (file.filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        head = [str(h or "").strip().lower() for h in rows[0]]
        return [dict(zip(head, r)) for r in rows[1:] if any(v not in (None, "") for v in r)]
    if name.endswith(".csv") or file.content_type in ("text/csv", "application/vnd.ms-excel"):
        text = data.decode("utf-8-sig", errors="replace")
        return [{(k or "").strip().lower(): v for k, v in r.items()} for r in csv.DictReader(io.StringIO(text))]
    raise HTTPException(415, "Upload a .csv or .xlsx file")


def _allowed_gps(ds, officer, block_id: int | None) -> list[dict]:
    blocks = [b["id"] for b in ds.list_blocks()]
    if block_id is not None:
        if not officer.can_see_block(block_id):
            raise HTTPException(403, "This block is not assigned to you")
        blocks = [block_id]
    return [g for b in blocks if officer.can_see_block(b) for g in ds.list_panchayats(b)]


@router.get("/template.csv", summary="Sample CSV for the farmer contacts upload")
def template():
    return Response(TEMPLATE, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="farmer-contacts-template.csv"'})


@router.post("/upload", summary="Officer uploads farmer contacts (CSV or Excel)")
async def upload(file: UploadFile, ds: DS, officer: OfficerDep, block_id: int | None = None):
    """Columns: name, mobile, panchayat (name or id), crop, language (te / hi / en).
    Rows are matched to panchayats the officer covers; a mobile already in that panchayat is updated."""
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 5 MB)")
    rows = _read_rows(file, data)
    if len(rows) > MAX_ROWS:
        raise HTTPException(413, f"Too many rows (max {MAX_ROWS})")
    gps = _allowed_gps(ds, officer, block_id)
    by_name = {}
    for g in gps:
        for k in ("name", "name_te", "name_hi"):
            if g.get(k):
                by_name[str(g[k]).strip().lower()] = g
    by_id = {g["id"]: g for g in gps}
    crops = set(engine.load_rules()["crops"])

    good, errors = {}, []
    for i, r in enumerate(rows, start=2):  # row 1 = header
        mobile = normalize_mobile(r.get("mobile") or r.get("phone") or r.get("mobile number"))
        if not mobile:
            errors.append({"row": i, "reason": "invalid_mobile"})
            continue
        key = str(r.get("panchayat") or r.get("gram panchayat") or r.get("village") or "").strip()
        gp = by_id.get(int(key)) if key.isdigit() else by_name.get(key.lower())
        if gp is None:
            errors.append({"row": i, "reason": "unknown_panchayat", "value": key[:40]})
            continue
        crop = str(r.get("crop") or "").strip().lower() or None
        lang = LANGS.get(str(r.get("language") or "te").strip().lower(), "te")
        good[(gp["id"], mobile)] = {"panchayat_id": gp["id"], "mobile": mobile,
                                    "name": (str(r.get("name")).strip()[:80] if r.get("name") else None),
                                    "crop": crop if crop in crops else None, "language": lang,
                                    "source": "upload", "consent_at": None}
    added, updated = ds.upsert_farmers(list(good.values()))
    return {"rows": len(rows), "added": added, "updated": updated,
            "duplicates": len(rows) - len(errors) - len(good), "errors": errors[:50], "error_count": len(errors)}


@router.get("", summary="Farmer contacts for the officer's panchayats (numbers masked)")
def list_farmers(ds: DS, officer: OfficerDep, block_id: int | None = None):
    gps = {g["id"]: g for g in _allowed_gps(ds, officer, block_id)}
    rows = [f for f in ds.list_farmers(list(gps)) if f.get("active", True)]
    counts: dict[int, int] = {}
    for f in rows:
        counts[f["panchayat_id"]] = counts.get(f["panchayat_id"], 0) + 1
    out = [{"id": f["id"], "panchayat_id": f["panchayat_id"],
            "panchayat": {k: gps[f["panchayat_id"]].get(k) for k in ("id", "name", "name_te", "name_hi")},
            "name": f.get("name"), "mobile_masked": mask(f["mobile"]), "crop": f.get("crop"),
            "language": f.get("language"), "source": f.get("source"), "consent_at": f.get("consent_at")}
           for f in sorted(rows, key=lambda f: (gps[f["panchayat_id"]]["name"], f.get("name") or ""))]
    return {"total": len(out), "self_registered": sum(f["source"] == "self" for f in out),
            "panchayats_covered": len(counts), "panchayats": len(gps), "per_panchayat": counts, "farmers": out}


@router.delete("/{farmer_id}", summary="Remove a farmer from the contact list")
def remove(farmer_id: int, ds: DS, officer: OfficerDep):
    ids = None if officer.block_ids is None else [g["id"] for b in officer.block_ids for g in ds.list_panchayats(b)]
    if not ds.set_farmer_active(farmer_id, False, ids):
        raise HTTPException(404, "Farmer not found")
    return {"ok": True}


class Subscribe(BaseModel):
    panchayat_id: int
    mobile: str = Field(examples=["9876543210"])
    name: str | None = Field(default=None, max_length=80)
    language: Literal["te", "hi", "en"] = "te"
    consent: bool


@router.post("/subscribe", status_code=201, summary='S7: farmer "Get alerts" sign-up (no login, needs consent)')
def subscribe(body: Subscribe, ds: DS):
    if not body.consent:
        raise HTTPException(422, "Consent is required")
    mobile = normalize_mobile(body.mobile)
    if not mobile:
        raise HTTPException(422, "Enter a valid 10-digit mobile number")
    if ds.get_panchayat(body.panchayat_id) is None:
        raise HTTPException(404, "Panchayat not found")
    added, _ = ds.upsert_farmers([{"panchayat_id": body.panchayat_id, "mobile": mobile, "name": body.name,
                                   "crop": None, "language": body.language, "source": "self", "consent_at": _now()}])
    return {"ok": True, "new": bool(added), "mobile_masked": mask(mobile)}


class Unsubscribe(BaseModel):
    panchayat_id: int
    mobile: str


@router.post("/unsubscribe", summary="Farmer stops alerts for this panchayat")
def unsubscribe(body: Unsubscribe, ds: DS):
    mobile = normalize_mobile(body.mobile)
    f = next((f for f in ds.list_farmers([body.panchayat_id]) if f["mobile"] == mobile), None) if mobile else None
    if f:
        ds.set_farmer_active(f["id"], False)
    return {"ok": True}  # same answer either way: do not reveal whether a number is registered
