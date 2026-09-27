import socket
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, advisory, alerts, blocks, farmers, feedback, forecast, officers, profiles, public, regions, share, validation
from app.core.config import get_settings
from app.core.datasource import begin_request_state, use_demo
from app.core.scheduler import start_scheduler
from app.core.supabase import is_configured

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Panchayat-level weather forecasts and agromet advisories, "
        "downscaled from IMD block-level forecasts (SIH 2026, PS 26074).\n\n"
        "Send header `X-Demo-Mode: 1` to force offline demo data. Responses carry "
        "`X-Data-Source` (supabase | demo) and `X-Data-Stale: 1` when Supabase failed and cached demo data was served."
    ),
    version="0.2.0",
)


start_scheduler()  # daily 06:00 IST pipeline, only if PIPELINE_SCHEDULE=true


@app.middleware("http")
async def data_source_headers(request: Request, call_next):
    state = begin_request_state()
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["X-Data-Source"] = state.source
        if state.stale:
            response.headers["X-Data-Stale"] = "1"
    return response


# Added after the middleware above so CORS wraps it (and its headers are exposed).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Data-Stale", "X-Data-Source"],
)

for r in (regions, blocks, forecast, advisory, share, validation, feedback, public, alerts, admin, profiles, farmers, officers):
    app.include_router(r.router, prefix="/api")


def lan_ip() -> str | None:
    """This machine's Wi-Fi/LAN address (so a phone on the same network can open the farmer page)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


@app.get("/health", tags=["system"], summary="Service health check")
@app.get("/api/health", tags=["system"], include_in_schema=False)
def health(request: Request) -> dict:
    """Service status, UTC time, Demo Mode and whether Supabase is configured."""
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "demo_mode": settings.demo_mode,
        "supabase_configured": is_configured(),
        "serving": "demo" if use_demo(request) else "supabase",
        "lan_ip": lan_ip(),
    }
