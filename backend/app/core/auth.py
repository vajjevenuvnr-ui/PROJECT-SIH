"""Officer authentication.

Officers sign in with Supabase Auth in the frontend and send "Authorization: Bearer <access token>".
The token is verified with Supabase. When the request is served from demo data and no token is sent,
a built-in demo officer is used so the demo works offline; demo writes stay in memory only.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from app.core.datasource import DataSource, get_datasource, use_demo
from app.core.supabase import get_supabase, is_configured


@dataclass
class Officer:
    id: str | None
    name: str
    role: str
    is_demo: bool = False
    block_ids: tuple[int, ...] | None = None  # None = all blocks (admin, demo)

    def can_see_block(self, block_id: int) -> bool:
        return self.block_ids is None or block_id in self.block_ids


DEMO_OFFICER = Officer(id=None, name="Lakshmi (demo officer)", role="officer", is_demo=True)


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def require_officer(request: Request, ds: DataSource = Depends(get_datasource)) -> Officer:
    token = _bearer(request)
    if token is None:
        if use_demo(request):
            return DEMO_OFFICER
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in as an extension officer")
    if not is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth is not configured on the server")
    try:
        user = get_supabase().auth.get_user(token).user
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session") from None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    rows = get_supabase().table("profiles").select("*").eq("id", user.id).execute().data
    profile = rows[0] if rows else None
    if not profile or profile.get("role") not in ("officer", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is not an extension officer")
    blocks = profile.get("block_ids") or []
    return Officer(id=user.id, name=profile.get("name") or user.email or "Officer", role=profile["role"],
                   block_ids=None if profile["role"] == "admin" or not blocks else tuple(blocks))
