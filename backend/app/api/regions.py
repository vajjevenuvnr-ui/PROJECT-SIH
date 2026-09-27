from fastapi import APIRouter, HTTPException

from app.api.deps import DS
from app.schemas.api import Region
from app.services.forecast import district_blocks_geojson, region

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/states", response_model=list[Region], summary="List states")
def states(ds: DS):
    return [region(s) for s in ds.list_states()]


@router.get("/districts", response_model=list[Region], summary="List districts of a state")
def districts(ds: DS, state: int | None = None):
    return [region(d) for d in ds.list_districts(state)]


@router.get("/blocks", response_model=list[Region], summary="List blocks (mandals) of a district")
def blocks(ds: DS, district: int | None = None):
    """`panchayat_count` = 0 means the block has no panchayat data yet (only the pilot block is covered)."""
    return [{**region(b), "panchayat_count": len(ds.list_panchayats(b["id"]))} for b in ds.list_blocks(district)]


@router.get("/districts/{district_id}/geojson", summary="District outline + block outlines (S1 mini map)")
def district_geojson(district_id: int, ds: DS):
    return district_blocks_geojson(ds, district_id)


@router.get("/blocks/{block_id}", response_model=Region, summary="One block")
def block(block_id: int, ds: DS):
    b = ds.get_block(block_id)
    if b is None:
        raise HTTPException(404, "Block not found")
    return region(b)
