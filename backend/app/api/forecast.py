from fastapi import APIRouter, Query

from app.api.deps import DS
from app.schemas.api import PanchayatForecast
from app.services import forecast as svc

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("/block/{block_id}", summary="IMD block forecast (Days 1-5, agromet bulletin fields)")
def block_forecast(block_id: int, ds: DS, day: int | None = Query(None, ge=1, le=5)):
    return svc.block_forecast(ds, block_id, day)


@router.get("/panchayat/{panchayat_id}", response_model=PanchayatForecast,
            summary="S3: 5-day panchayat forecast with block comparison, confidence and alerts")
def panchayat_forecast(panchayat_id: int, ds: DS):
    return svc.panchayat_forecast(ds, panchayat_id)
