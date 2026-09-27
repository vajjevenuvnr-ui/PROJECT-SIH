"""Officer accounts. Public sign-up is disabled in Supabase; only an admin (district / DAMU head) adds officers.

Invite flow: the admin enters an official email, name and blocks -> Supabase creates the account and an invite
link -> the officer opens it and sets a password on /set-password. The link is returned to the admin as well,
because Supabase's built-in mailer only delivers to project team members until custom SMTP is configured.
"""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import AdminDep, DS, OfficerDep
from app.core.config import get_settings
from app.core.supabase import get_supabase, is_configured

router = APIRouter(tags=["officers"])


@router.get("/me", summary="The signed-in officer: name, role and assigned blocks")
def me(officer: OfficerDep):
    return {"id": officer.id, "name": officer.name, "role": officer.role, "is_demo": officer.is_demo,
            "block_ids": list(officer.block_ids) if officer.block_ids is not None else None}


def allowed_email(email: str) -> bool:
    domains = [d.strip().lower() for d in get_settings().officer_email_domains.split(",") if d.strip()]
    host = email.rsplit("@", 1)[-1].lower()
    return not domains or any(host == d or host.endswith("." + d) for d in domains)


def _live():
    if not is_configured():
        raise HTTPException(503, "Officer accounts need the live database (Supabase); not available in Demo Mode")
    return get_supabase()


class OfficerIn(BaseModel):
    email: str = Field(examples=["aeo.gajwel@telangana.gov.in"], max_length=120)
    name: str = Field(min_length=2, max_length=80)
    role: Literal["officer", "admin"] = "officer"
    block_ids: list[int] = Field(default_factory=list)


class OfficerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    role: Literal["officer", "admin"] | None = None
    block_ids: list[int] | None = None


def _check_blocks(ds, block_ids: list[int]) -> list[int]:
    known = {b["id"] for b in ds.list_blocks()}
    bad = [b for b in block_ids if b not in known]
    if bad:
        raise HTTPException(422, f"Unknown block ids: {bad}")
    return sorted(set(block_ids))


@router.get("/officers", summary="Admin: all officer accounts")
def list_officers(admin: AdminDep):
    sb = _live()
    profiles = {p["id"]: p for p in sb.table("profiles").select("*").execute().data}
    users = sb.auth.admin.list_users(page=1, per_page=1000)
    out = []
    for u in users:
        p = profiles.get(u.id)
        if not p:
            continue
        out.append({"id": u.id, "email": u.email, "name": p.get("name"), "role": p.get("role"),
                    "block_ids": p.get("block_ids") or [], "last_sign_in_at": u.last_sign_in_at,
                    "status": "active" if u.last_sign_in_at or u.email_confirmed_at else "invited",
                    "is_you": u.id == admin.id})
    return sorted(out, key=lambda o: (o["role"] != "admin", o["name"] or ""))


@router.post("/officers/invite", status_code=201, summary="Admin: invite an officer by official email")
def invite(body: OfficerIn, ds: DS, admin: AdminDep):
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email):
        raise HTTPException(422, "Enter a valid email address")
    if not allowed_email(email):
        raise HTTPException(422, f"Use an official email ({get_settings().officer_email_domains})")
    blocks = _check_blocks(ds, body.block_ids)
    if body.role == "officer" and not blocks:
        raise HTTPException(422, "Assign at least one block")
    sb = _live()
    existing = next((u for u in sb.auth.admin.list_users(page=1, per_page=1000) if (u.email or "").lower() == email), None)
    if existing and (existing.last_sign_in_at or existing.email_confirmed_at):
        raise HTTPException(409, "An officer with this email already exists")  # re-inviting only for pending invites
    redirect = get_settings().public_app_url.rstrip("/") + "/set-password"
    try:
        res = sb.auth.admin.generate_link({"type": "invite", "email": email,
                                           "options": {"data": {"name": body.name}, "redirect_to": redirect}})
    except Exception as exc:
        msg = str(exc)
        if "already" in msg.lower() or "registered" in msg.lower():
            raise HTTPException(409, "An account with this email already exists") from None
        raise HTTPException(502, f"Could not create the invite: {msg}") from None
    user = res.user
    sb.table("profiles").upsert({"id": user.id, "name": body.name, "role": body.role, "block_ids": blocks}).execute()
    return {"id": user.id, "email": email, "name": body.name, "role": body.role, "block_ids": blocks,
            "invite_link": res.properties.action_link, "expires_hours": 24}


@router.patch("/officers/{user_id}", summary="Admin: change an officer's name, role or blocks")
def update(user_id: str, body: OfficerPatch, ds: DS, admin: AdminDep):
    sb = _live()
    patch = body.model_dump(exclude_none=True)
    if "block_ids" in patch:
        patch["block_ids"] = _check_blocks(ds, patch["block_ids"])
    if user_id == admin.id and patch.get("role") == "officer":
        raise HTTPException(409, "You cannot remove your own admin role")
    rows = sb.table("profiles").update(patch).eq("id", user_id).execute().data
    if not rows:
        raise HTTPException(404, "Officer not found")
    return rows[0]


@router.delete("/officers/{user_id}", summary="Admin: remove an officer (deletes the login)")
def remove(user_id: str, admin: AdminDep):
    if user_id == admin.id:
        raise HTTPException(409, "You cannot remove your own account")
    sb = _live()
    try:
        sb.auth.admin.delete_user(user_id)  # profile row is deleted by the foreign key cascade
    except Exception:
        raise HTTPException(404, "Officer not found") from None
    return {"ok": True}
