"""Data access for the API.

Two implementations share one interface and return plain dicts:
  * DemoSource     - reads backend/data/demo/*.json (offline; writes kept in memory)
  * SupabaseSource - reads/writes Supabase via the service-role key

FallbackSource wraps Supabase: if a call fails it serves DemoSource instead and marks the
request stale, so the UI can show a "Cached data" label instead of an empty screen.

Selection per request (see get_datasource):
  DEMO_MODE=true, header "X-Demo-Mode: 1", or Supabase not configured -> DemoSource
  otherwise -> FallbackSource(Supabase -> Demo)
"""

from __future__ import annotations

import contextvars
import os
import copy
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Request

from app.core.config import get_settings
from app.core.supabase import get_supabase, is_configured

log = logging.getLogger(__name__)

# Demo Mode data. The pipeline (Phase 7) may replace data/demo/forecast.json with a real run;
# tests pin PC_DEMO_DIR to data/seed so they always see the fixed synthetic seed.
DEMO_DIR = Path(os.environ.get("PC_DEMO_DIR") or Path(__file__).resolve().parents[2] / "data" / "demo")


# ---------------------------------------------------------------------------
# Per-request state (a mutable object so changes made in worker threads are seen
# by the middleware that set it)
# ---------------------------------------------------------------------------
@dataclass
class RequestDataState:
    source: str = "demo"
    stale: bool = False


_request_state: contextvars.ContextVar[RequestDataState | None] = contextvars.ContextVar(
    "request_data_state", default=None
)


def begin_request_state() -> RequestDataState:
    state = RequestDataState()
    _request_state.set(state)
    return state


def _state() -> RequestDataState | None:
    return _request_state.get()


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
class DataSource:
    name = "base"

    # Regions
    def list_states(self) -> list[dict]: raise NotImplementedError
    def list_districts(self, state_id: int | None = None) -> list[dict]: raise NotImplementedError
    def get_district(self, district_id: int) -> dict | None: raise NotImplementedError
    def list_blocks(self, district_id: int | None = None) -> list[dict]: raise NotImplementedError
    def get_block(self, block_id: int) -> dict | None: raise NotImplementedError
    def list_panchayats(self, block_id: int) -> list[dict]: raise NotImplementedError
    def get_panchayat(self, panchayat_id: int) -> dict | None: raise NotImplementedError

    # Forecasts
    def latest_run(self) -> dict | None: raise NotImplementedError
    def block_forecasts(self, run_id: int, block_id: int) -> list[dict]: raise NotImplementedError
    def panchayat_forecasts(self, run_id: int, panchayat_ids: list[int]) -> list[dict]: raise NotImplementedError

    # Validation
    def list_stations(self) -> list[dict]: raise NotImplementedError
    def validation_metrics(self, variable: str | None = None) -> list[dict]: raise NotImplementedError
    def backtest_events(self) -> list[dict]: raise NotImplementedError

    # Advisories and delivery
    def insert_advisory(self, row: dict) -> dict: raise NotImplementedError
    def get_advisory(self, advisory_id: int) -> dict | None: raise NotImplementedError
    def update_advisory(self, advisory_id: int, patch: dict) -> dict | None: raise NotImplementedError
    def latest_advisory(self, panchayat_id: int, statuses: tuple[str, ...]) -> dict | None: raise NotImplementedError
    def insert_share_log(self, row: dict) -> dict: raise NotImplementedError
    def list_share_log(self, advisory_id: int | None = None) -> list[dict]: raise NotImplementedError
    def insert_feedback(self, row: dict) -> dict: raise NotImplementedError

    # Extreme-weather alerts (Phase 6b)
    def list_alert_acks(self) -> dict[str, dict]: raise NotImplementedError
    def ack_alert(self, alert_id: str, officer: str | None) -> dict: raise NotImplementedError
    def insert_alert_dispatch(self, row: dict) -> dict: raise NotImplementedError
    def list_alert_dispatch(self, alert_id: str | None = None) -> list[dict]: raise NotImplementedError
    def upsert_push_subscription(self, row: dict) -> dict: raise NotImplementedError
    def list_push_subscriptions(self, panchayat_ids: list[int]) -> list[dict]: raise NotImplementedError
    def delete_push_subscription(self, endpoint: str) -> None: raise NotImplementedError

    def previous_forecast(self, panchayat_ids: list[int]) -> tuple[dict | None, list[dict]]:
        """(previous run, its panchayat rows) to compare against for change notifications."""
        return None, []

    def list_feedback(self, panchayat_ids: list[int] | None = None) -> list[dict]:
        raise NotImplementedError

    # Farmer contacts (personal data: never exposed unmasked by the API)
    def list_farmers(self, panchayat_ids: list[int]) -> list[dict]: raise NotImplementedError
    def upsert_farmers(self, rows: list[dict]) -> tuple[int, int]: raise NotImplementedError
    def set_farmer_active(self, farmer_id: int, active: bool, panchayat_ids: list[int] | None = None) -> bool:
        raise NotImplementedError

    # Crop profiles (Phase 10)
    def get_crop_profiles(self) -> dict[int, dict]: raise NotImplementedError
    def set_crop_profile(self, row: dict) -> dict: raise NotImplementedError

    # Demo-only "Simulate extreme event"
    def simulate_extreme(self, center_panchayat_id: int, day: int = 2) -> dict:
        raise NotImplementedError("Simulation is only available in Demo Mode")

    def reset_simulation(self) -> None:
        raise NotImplementedError("Simulation is only available in Demo Mode")

    def simulation_state(self) -> dict | None:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Demo (offline JSON)
# ---------------------------------------------------------------------------
class DemoSource(DataSource):
    name = "demo"

    def __init__(self, directory: Path = DEMO_DIR):
        def load(name: str) -> Any:
            return json.loads((directory / name).read_text(encoding="utf-8"))

        regions = load("regions.json")
        self._states = regions["states"]
        self._districts = regions["districts"]
        self._blocks = regions["blocks"]
        self._panchayats = [
            {**f["properties"], "geom": f["geometry"]} for f in load("panchayats.geojson")["features"]
        ]
        fc = load("forecast.json")
        self._run = fc["run"]
        self._prev = fc.get("previous")  # {"run": ..., "panchayat_forecasts": [...]} written by the pipeline
        self._block_fc = fc["block_forecasts"]
        self._gp_fc = fc["panchayat_forecasts"]
        st = load("stations.json")
        self._stations = st["stations"]
        val = load("validation.json")
        self._metrics = val["metrics"]
        self._backtests = val["backtest_events"]

        # In-memory writes (reset on restart)
        self._lock = threading.Lock()
        self._advisories: dict[int, dict] = {}
        self._share_log: list[dict] = []
        self._feedback: list[dict] = []
        self._ids = {"advisory": 0, "share": 0, "feedback": 0, "dispatch": 0, "push": 0, "farmer": 0}
        self._farmers: list[dict] = []
        self._acks: dict[str, dict] = {}
        self._dispatch: list[dict] = []
        self._push: dict[str, dict] = {}  # endpoint -> subscription row
        self._profiles: dict[int, dict] = {}
        # Simulation overlay: {"version", "center", "day", "block_id", "pf": {(gp, day): patch}, "bf": {day: patch}}
        self._sim: dict | None = None
        self._sim_version = 0

    @staticmethod
    def _c(x):
        return copy.deepcopy(x)

    def list_states(self):
        return self._c(self._states)

    def list_districts(self, state_id=None):
        return self._c([d for d in self._districts if state_id is None or d["state_id"] == state_id])

    def get_district(self, district_id):
        return self._c(next((d for d in self._districts if d["id"] == district_id), None))

    def list_blocks(self, district_id=None):
        return self._c([b for b in self._blocks if district_id is None or b["district_id"] == district_id])

    def get_block(self, block_id):
        return self._c(next((b for b in self._blocks if b["id"] == block_id), None))

    def list_panchayats(self, block_id):
        return self._c([p for p in self._panchayats if p["block_id"] == block_id])

    def get_panchayat(self, panchayat_id):
        return self._c(next((p for p in self._panchayats if p["id"] == panchayat_id), None))

    def latest_run(self):
        run = self._c(self._run)
        if self._sim:
            run.update({"source": "simulated", "revision": self._sim["version"],
                        "notes": "Demo Mode: simulated extreme event (not a real forecast)."})
        return run

    def block_forecasts(self, run_id, block_id):
        rows = self._c([r for r in self._block_fc if r["run_id"] == run_id and r["block_id"] == block_id])
        if self._sim and block_id == self._sim["block_id"]:
            for r in rows:
                r.update(self._sim["bf"].get(r["day"], {}))
        return rows

    def panchayat_forecasts(self, run_id, panchayat_ids):
        ids = set(panchayat_ids)
        rows = self._c([r for r in self._gp_fc if r["run_id"] == run_id and r["panchayat_id"] in ids])
        if self._sim:
            for r in rows:
                r.update(self._sim["pf"].get((r["panchayat_id"], r["day"]), {}))
        return rows

    def previous_forecast(self, panchayat_ids):
        ids = set(panchayat_ids)
        if self._sim:  # compare the simulated event with the forecast before it
            base = self._c(self._run)
            return base, self._c([r for r in self._gp_fc if r["panchayat_id"] in ids])
        if self._prev:
            return self._c(self._prev["run"]), self._c([r for r in self._prev["panchayat_forecasts"] if r["panchayat_id"] in ids])
        return None, []

    # ---- simulation (Demo Mode only) -----------------------------------------
    # Very heavy rain cell centred on one GP, tapering to its nearest neighbours (mm on the chosen day).
    SIM_RAIN = [132.0, 118.0, 101.0, 84.0, 71.0, 58.0, 47.0]

    def simulate_extreme(self, center_panchayat_id, day=2):
        center = next((p for p in self._panchayats if p["id"] == center_panchayat_id), None)
        if center is None:
            raise KeyError(center_panchayat_id)
        cx, cy = center["centroid"]["coordinates"]
        block_gps = [p for p in self._panchayats if p["block_id"] == center["block_id"]]
        block_ids = {p["id"] for p in block_gps}

        def dist(p):
            x, y = p["centroid"]["coordinates"]
            return (x - cx) ** 2 + (y - cy) ** 2

        by_dist = sorted(block_gps, key=dist)
        base = {r["panchayat_id"]: r for r in self._gp_fc if r["day"] == day and r["panchayat_id"] in block_ids}
        pf = {}
        for i, gp in enumerate(by_dist[: len(self.SIM_RAIN)]):
            mm = self.SIM_RAIN[i]
            b = base[gp["id"]]
            pf[(gp["id"], day)] = {
                "rain_mm": mm, "rain_min": round(mm * 0.7, 1), "rain_max": round(mm * 1.35, 1),
                "rain_prob_10mm": 0.97 if mm >= 64.5 else 0.85, "rain_prob_2_5mm": 0.99,
                "tmax": round(b["tmax"] - 2.0, 1), "rh": 96.0, "wind_kmh": round(max(b["wind_kmh"], 22.0), 1),
                "confidence": "high" if i < 3 else "medium",
            }
        # Mass consistency: the block value becomes the mean of the (patched) panchayat values.
        rows = [{**r, **pf.get((gid, day), {})} for gid, r in base.items()]

        def mean(k):
            return round(sum(r[k] for r in rows) / len(rows), 2)

        bf = {day: {"rain_mm": mean("rain_mm"), "tmax": mean("tmax"), "wind_kmh": mean("wind_kmh"),
                    "rh_max": 98.0, "rh_min": 80.0, "cloud_okta": 8}}
        with self._lock:
            self._sim_version += 1
            self._sim = {"version": self._sim_version, "center": center_panchayat_id, "day": day,
                         "block_id": center["block_id"], "pf": pf, "bf": bf}
        return {"active": True, "version": self._sim_version, "center_panchayat_id": center_panchayat_id,
                "day": day, "affected": [gid for gid, _ in pf], "block_rain_mm": bf[day]["rain_mm"]}

    def reset_simulation(self):
        with self._lock:
            self._sim = None

    def simulation_state(self):
        if not self._sim:
            return None
        return {k: v for k, v in self._sim.items() if k not in ("pf", "bf")}

    def list_stations(self):
        return self._c(self._stations)

    def validation_metrics(self, variable=None):
        return self._c([m for m in self._metrics if variable is None or m["variable"] == variable])

    def backtest_events(self):
        return self._c(self._backtests)

    def _next(self, key: str) -> int:
        self._ids[key] += 1
        return self._ids[key]

    def insert_advisory(self, row):
        with self._lock:
            rec = {"id": self._next("advisory"), "created_at": _now(), "status": "draft", "edited_text": None,
                   "approved_by": None, **row}
            self._advisories[rec["id"]] = rec
            return self._c(rec)

    def get_advisory(self, advisory_id):
        return self._c(self._advisories.get(advisory_id))

    def update_advisory(self, advisory_id, patch):
        with self._lock:
            if advisory_id not in self._advisories:
                return None
            self._advisories[advisory_id].update(patch)
            return self._c(self._advisories[advisory_id])

    def latest_advisory(self, panchayat_id, statuses):
        recs = [a for a in self._advisories.values() if a["panchayat_id"] == panchayat_id and a["status"] in statuses]
        return self._c(max(recs, key=lambda a: a["id"])) if recs else None

    def insert_share_log(self, row):
        with self._lock:
            rec = {"id": self._next("share"), "sent_at": _now(), **row}
            self._share_log.append(rec)
            return self._c(rec)

    def list_share_log(self, advisory_id=None):
        rows = [r for r in self._share_log if advisory_id is None or r["advisory_id"] == advisory_id]
        return self._c(sorted(rows, key=lambda r: r["id"], reverse=True))

    def insert_feedback(self, row):
        with self._lock:
            rec = {"id": self._next("feedback"), "created_at": _now(), **row}
            self._feedback.append(rec)
            return self._c(rec)

    def list_feedback(self, panchayat_ids=None):
        ids = set(panchayat_ids or [])
        return self._c([f for f in self._feedback if not ids or f["panchayat_id"] in ids])

    def list_farmers(self, panchayat_ids):
        ids = set(panchayat_ids)
        return self._c([f for f in self._farmers if f["panchayat_id"] in ids])

    def upsert_farmers(self, rows):
        added = updated = 0
        with self._lock:
            idx = {(f["panchayat_id"], f["mobile"]): f for f in self._farmers}
            for r in rows:
                cur = idx.get((r["panchayat_id"], r["mobile"]))
                if cur:
                    cur.update({k: v for k, v in r.items() if v is not None}, active=True, updated_at=_now())
                    updated += 1
                else:
                    rec = {"id": self._next("farmer"), "active": True, "created_at": _now(), "updated_at": _now(), **r}
                    self._farmers.append(rec)
                    idx[(r["panchayat_id"], r["mobile"])] = rec
                    added += 1
        return added, updated

    def set_farmer_active(self, farmer_id, active, panchayat_ids=None):
        with self._lock:
            for f in self._farmers:
                if f["id"] == farmer_id and (panchayat_ids is None or f["panchayat_id"] in panchayat_ids):
                    f.update(active=active, updated_at=_now())
                    return True
        return False

    def get_crop_profiles(self):
        return self._c(self._profiles)

    def set_crop_profile(self, row):
        with self._lock:
            self._profiles[row["panchayat_id"]] = dict(row)
            return self._c(row)

    def list_alert_acks(self):
        return self._c(self._acks)

    def ack_alert(self, alert_id, officer):
        with self._lock:
            rec = {"alert_id": alert_id, "acknowledged_by": officer, "acknowledged_at": _now()}
            self._acks[alert_id] = rec
            return self._c(rec)

    def insert_alert_dispatch(self, row):
        with self._lock:
            rec = {"id": self._next("dispatch"), "sent_at": _now(), **row}
            self._dispatch.append(rec)
            return self._c(rec)

    def list_alert_dispatch(self, alert_id=None):
        rows = [r for r in self._dispatch if alert_id is None or r["alert_id"] == alert_id]
        return self._c(sorted(rows, key=lambda r: r["id"], reverse=True))

    def upsert_push_subscription(self, row):
        with self._lock:
            old = self._push.get(row["endpoint"])
            rec = {"id": old["id"] if old else self._next("push"), "created_at": _now(), **row}
            self._push[row["endpoint"]] = rec
            return self._c(rec)

    def list_push_subscriptions(self, panchayat_ids):
        ids = set(panchayat_ids)
        return self._c([r for r in self._push.values() if r["panchayat_id"] in ids])

    def delete_push_subscription(self, endpoint):
        with self._lock:
            self._push.pop(endpoint, None)


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
class SupabaseSource(DataSource):
    """Reads geometry through the v_* views (0002_api_views.sql), which return GeoJSON."""

    name = "supabase"
    TTL_S = 60.0  # forecasts change once a day; a short cache keeps map switching fast

    def __init__(self):
        self._cache: dict[tuple, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    @property
    def db(self):
        return get_supabase()

    def _cached(self, key: tuple, fn):
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < self.TTL_S:
                return copy.deepcopy(hit[1])
        value = fn()
        with self._lock:
            self._cache[key] = (now, value)
        return copy.deepcopy(value)

    def _select(self, table: str, **eq) -> list[dict]:
        q = self.db.table(table).select("*")
        for k, v in eq.items():
            if v is not None:
                q = q.eq(k, v)
        return q.execute().data

    def list_states(self):
        return self._cached(("states",), lambda: self._select("states"))

    def list_districts(self, state_id=None):
        return self._cached(("districts", state_id), lambda: self._select("v_districts", state_id=state_id))

    def get_district(self, district_id):
        rows = self._cached(("district", district_id), lambda: self._select("v_districts", id=district_id))
        return rows[0] if rows else None

    def list_blocks(self, district_id=None):
        return self._cached(("blocks", district_id), lambda: self._select("v_blocks", district_id=district_id))

    def get_block(self, block_id):
        rows = self._cached(("block", block_id), lambda: self._select("v_blocks", id=block_id))
        return rows[0] if rows else None

    def list_panchayats(self, block_id):
        return self._cached(("gps", block_id), lambda: self._select("v_panchayats", block_id=block_id))

    def get_panchayat(self, panchayat_id):
        rows = self._cached(("gp", panchayat_id), lambda: self._select("v_panchayats", id=panchayat_id))
        return rows[0] if rows else None

    def latest_run(self):
        def fn():
            rows = (self.db.table("forecast_runs").select("*").in_("status", ["ok", "stale"])
                    .order("issued_at", desc=True).limit(1).execute().data)
            return rows[0] if rows else None
        return self._cached(("latest_run",), fn)

    def block_forecasts(self, run_id, block_id):
        return self._cached(("bf", run_id, block_id),
                            lambda: self._select("block_forecasts", run_id=run_id, block_id=block_id))

    def panchayat_forecasts(self, run_id, panchayat_ids):
        key = ("pf", run_id, tuple(sorted(panchayat_ids)))
        return self._cached(key, lambda: self.db.table("panchayat_forecasts").select("*")
                            .eq("run_id", run_id).in_("panchayat_id", list(panchayat_ids)).execute().data)

    def list_stations(self):
        return self._cached(("stations",), lambda: self._select("v_aws_stations"))

    def validation_metrics(self, variable=None):
        return self._cached(("metrics", variable), lambda: self._select("validation_metrics", variable=variable))

    def backtest_events(self):
        return self._cached(("backtests",), lambda: self._select("backtest_events"))

    def insert_advisory(self, row):
        return self.db.table("advisories").insert(row).execute().data[0]

    def get_advisory(self, advisory_id):
        rows = self._select("advisories", id=advisory_id)
        return rows[0] if rows else None

    def update_advisory(self, advisory_id, patch):
        rows = self.db.table("advisories").update(patch).eq("id", advisory_id).execute().data
        return rows[0] if rows else None

    def latest_advisory(self, panchayat_id, statuses):
        rows = (self.db.table("advisories").select("*").eq("panchayat_id", panchayat_id)
                .in_("status", list(statuses)).order("id", desc=True).limit(1).execute().data)
        return rows[0] if rows else None

    def insert_share_log(self, row):
        return self.db.table("share_log").insert(row).execute().data[0]

    def list_share_log(self, advisory_id=None):
        q = self.db.table("share_log").select("*").order("id", desc=True)
        if advisory_id is not None:
            q = q.eq("advisory_id", advisory_id)
        return q.execute().data

    def insert_feedback(self, row):
        return self.db.table("rain_feedback").insert(row).execute().data[0]


class _SupabaseAlerts:
    """Alert tables for SupabaseSource (see migrations/0003_alerts.sql)."""

    def list_alert_acks(self):
        return {r["alert_id"]: r for r in self.db.table("alert_acks").select("*").execute().data}

    def ack_alert(self, alert_id, officer):
        row = {"alert_id": alert_id, "acknowledged_by": officer, "acknowledged_at": _now()}
        return self.db.table("alert_acks").upsert(row).execute().data[0]

    def insert_alert_dispatch(self, row):
        return self.db.table("alert_dispatch_log").insert(row).execute().data[0]

    def list_alert_dispatch(self, alert_id=None):
        q = self.db.table("alert_dispatch_log").select("*").order("id", desc=True)
        if alert_id is not None:
            q = q.eq("alert_id", alert_id)
        return q.execute().data

    def upsert_push_subscription(self, row):
        return self.db.table("push_subscriptions").upsert(row, on_conflict="endpoint").execute().data[0]

    def list_push_subscriptions(self, panchayat_ids):
        return self.db.table("push_subscriptions").select("*").in_("panchayat_id", list(panchayat_ids)).execute().data

    def delete_push_subscription(self, endpoint):
        self.db.table("push_subscriptions").delete().eq("endpoint", endpoint).execute()

    def list_feedback(self, panchayat_ids=None):
        q = self.db.table("rain_feedback").select("*")
        if panchayat_ids:
            q = q.in_("panchayat_id", list(panchayat_ids))
        return q.execute().data

    def list_farmers(self, panchayat_ids):
        return self.db.table("farmers").select("*").in_("panchayat_id", list(panchayat_ids)).execute().data

    def upsert_farmers(self, rows):
        if not rows:
            return 0, 0
        keys = {(r["panchayat_id"], r["mobile"]) for r in rows}
        existing = {(f["panchayat_id"], f["mobile"]) for f in self.list_farmers(list({k[0] for k in keys}))}
        cols = ("panchayat_id", "mobile", "name", "crop", "language", "source", "consent_at")
        payload = [{**{k: r.get(k) for k in cols}, "active": True, "updated_at": _now()} for r in rows]  # same keys per row
        self.db.table("farmers").upsert(payload, on_conflict="panchayat_id,mobile").execute()
        updated = len(keys & existing)
        return len(keys) - updated, updated

    def set_farmer_active(self, farmer_id, active, panchayat_ids=None):
        q = self.db.table("farmers").update({"active": active, "updated_at": _now()}).eq("id", farmer_id)
        if panchayat_ids is not None:
            q = q.in_("panchayat_id", list(panchayat_ids))
        return bool(q.execute().data)

    def get_crop_profiles(self):
        return {r["panchayat_id"]: r for r in self.db.table("crop_profiles").select("*").execute().data}

    def set_crop_profile(self, row):
        return self.db.table("crop_profiles").upsert(row, on_conflict="panchayat_id").execute().data[0]


for _name in ("list_alert_acks", "ack_alert", "insert_alert_dispatch", "list_alert_dispatch",
              "upsert_push_subscription", "list_push_subscriptions", "delete_push_subscription",
              "get_crop_profiles", "set_crop_profile", "list_feedback",
              "list_farmers", "upsert_farmers", "set_farmer_active"):
    setattr(SupabaseSource, _name, getattr(_SupabaseAlerts, _name))


class FallbackSource(DataSource):
    """Try the primary source; on any error serve the fallback and mark the request stale."""

    def __init__(self, primary: DataSource, fallback: DataSource):
        self.primary, self.fallback = primary, fallback
        self.name = primary.name

    def __getattribute__(self, item):
        if item.startswith("_") or item in ("primary", "fallback", "name"):
            return object.__getattribute__(self, item)
        primary = object.__getattribute__(self, "primary")
        fallback = object.__getattribute__(self, "fallback")
        p_fn, f_fn = getattr(primary, item), getattr(fallback, item)
        if not callable(p_fn):
            return p_fn

        def call(*args, **kwargs):
            try:
                return p_fn(*args, **kwargs)
            except Exception as exc:  # network, auth, missing view...
                log.warning("Supabase %s failed (%s); serving demo data", item, exc)
                st = _state()
                if st:
                    st.stale = True
                    st.source = fallback.name
                return f_fn(*args, **kwargs)

        return call


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------
_demo: DemoSource | None = None
_demo_mtime: float = 0.0
_demo_lock = threading.Lock()


def demo_source() -> DemoSource:
    """Shared DemoSource, reloaded when the JSON files change (e.g. after re-running the seed or pipeline).
    Note: reloading clears in-memory demo writes."""
    global _demo, _demo_mtime
    mtime = max((p.stat().st_mtime for p in DEMO_DIR.glob("*.json*")), default=0.0)
    with _demo_lock:
        if _demo is None or mtime > _demo_mtime:
            _demo, _demo_mtime = DemoSource(), mtime
        return _demo


@lru_cache
def supabase_source() -> SupabaseSource:
    return SupabaseSource()


def use_demo(request: Request | None = None) -> bool:
    if get_settings().demo_mode or not is_configured():
        return True
    return request is not None and request.headers.get("x-demo-mode") == "1"


def get_datasource(request: Request) -> DataSource:
    """FastAPI dependency: pick the data source for this request."""
    st = _state()
    if use_demo(request):
        if st:
            st.source = "demo"
        return demo_source()
    if st:
        st.source = "supabase"
    return FallbackSource(supabase_source(), demo_source())
