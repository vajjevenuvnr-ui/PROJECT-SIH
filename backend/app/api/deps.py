from typing import Annotated

from fastapi import Depends, HTTPException, Query

from app.core.auth import Officer, require_officer
from app.core.datasource import DataSource, get_datasource
from app.schemas.api import Variable

DS = Annotated[DataSource, Depends(get_datasource)]
OfficerDep = Annotated[Officer, Depends(require_officer)]


def require_admin(officer: OfficerDep) -> Officer:
    if officer.role != "admin":
        raise HTTPException(403, "Only an admin can manage officer accounts")
    return officer


AdminDep = Annotated[Officer, Depends(require_admin)]


# Officers act (send, approve, edit) only in their assigned blocks. Viewing forecasts stays open to all.
NOT_YOURS = "This block is not assigned to you"


def ensure_block(officer: Officer, block_id: int) -> None:
    if not officer.can_see_block(block_id):
        raise HTTPException(403, NOT_YOURS)


def ensure_panchayat(ds: DataSource, officer: Officer, panchayat_id: int) -> dict:
    gp = ds.get_panchayat(panchayat_id)
    if gp is None:
        raise HTTPException(404, "Panchayat not found")
    ensure_block(officer, gp["block_id"])
    return gp
VarQuery = Annotated[Variable, Query(description="rain | tmax | tmin | rh | wind")]
DayQuery = Annotated[int, Query(ge=1, le=5, description="Forecast day 1-5")]
