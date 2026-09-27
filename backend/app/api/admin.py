from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import OfficerDep
from app.core import scheduler

router = APIRouter(prefix="/admin", tags=["admin"])


class RunRequest(BaseModel):
    replay: date | None = Field(None, description="Issue date of a past event to replay; empty = live forecast")
    publish_demo: bool = Field(False, description="Serve the result in Demo Mode (replaces data/demo/forecast.json)")


@router.post("/run-pipeline", status_code=202, summary="Run the downscaling pipeline now (background)")
def run_pipeline(body: RunRequest, officer: OfficerDep):
    if not scheduler.start_in_background(body.replay, body.publish_demo):
        raise HTTPException(409, "A pipeline run is already in progress")
    return {"started": True, **scheduler.STATE}


@router.get("/pipeline-status", summary="Last pipeline run: status, timings, errors")
def pipeline_status():
    return scheduler.STATE
