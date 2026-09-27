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
VarQuery = Annotated[Variable, Query(description="rain | tmax | tmin | rh | wind")]
DayQuery = Annotated[int, Query(ge=1, le=5, description="Forecast day 1-5")]
