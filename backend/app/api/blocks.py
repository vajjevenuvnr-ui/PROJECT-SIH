from fastapi import APIRouter, Response

from app.api.deps import DS, DayQuery, VarQuery
from app.schemas.api import BlockSummary, Insight
from app.services import forecast as svc

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.get("/{block_id}/summary", response_model=BlockSummary,
            summary="S1 cards: panchayat count, active alerts, latest run status")
def summary(block_id: int, ds: DS):
    return svc.block_summary(ds, block_id)


@router.get("/{block_id}/geojson", summary="Block outline as GeoJSON (S2 left map)")
def block_geojson(block_id: int, ds: DS):
    return svc.block_geojson(ds, block_id)


@router.get("/{block_id}/panchayats/geojson",
            summary="Panchayat choropleth for one variable and day (S2 right map)")
def panchayats_geojson(block_id: int, ds: DS, var: VarQuery = "rain", day: DayQuery = 1):
    """Each feature carries value, min/max, rain probability (>10 mm) and confidence.
    `meta.block_value` is the IMD block value for the same variable and day."""
    return svc.panchayats_geojson(ds, block_id, var, day)


@router.get("/{block_id}/panchayats/forecast",
            summary="S2 bundle: every panchayat x 5 days x 5 variables, block outline and block values")
def panchayats_forecast(block_id: int, ds: DS):
    """One request for the whole split map. `meta.block_values[day-1][var]` is the IMD block value;
    each feature's `properties.days` holds that panchayat's values for Days 1-5."""
    return svc.panchayats_forecast_bundle(ds, block_id)


@router.get("/{block_id}/bulletin.pdf", summary="GKMS-style agromet bulletin (PDF) for the block")
def bulletin(block_id: int, ds: DS):
    from app.services.bulletin import build_pdf

    pdf = build_pdf(ds, block_id)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="agromet-bulletin-block{block_id}.pdf"'})


@router.get("/{block_id}/insight", response_model=Insight,
            summary='Insight chip, e.g. "Rain varies 0-38 mm across 24 GPs; block says 8 mm"')
def insight(block_id: int, ds: DS, var: VarQuery = "rain", day: DayQuery = 1):
    return svc.insight(ds, block_id, var, day)
