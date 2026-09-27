"""Response and request models (they also document the API at /docs)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Variable = Literal["rain", "tmax", "tmin", "rh", "wind"]
Confidence = Literal["high", "medium", "low"]
Lang = Literal["en", "te", "hi"]


class Region(BaseModel):
    id: int
    lgd_code: str
    name: str
    name_te: str | None = None
    name_hi: str | None = None
    panchayat_count: int | None = Field(None, description="Blocks only: panchayats with forecasts (0 = not covered yet)")


class RunInfo(BaseModel):
    id: int
    issued_at: str
    source: str
    source_label: str
    status: str
    duration_s: float | None = None


class AlertOut(BaseModel):
    type: str
    severity: Literal["watch", "warning"]
    day: int
    date: str
    title: str
    detail: str
    panchayat_id: int | None = None
    panchayat_name: str | None = None


class BlockSummary(BaseModel):
    block: Region
    district: Region | None
    panchayat_count: int
    active_alerts: int
    alerts: list[AlertOut]
    run: RunInfo | None
    days: list[dict] = Field(description="Day number, date and weekday for Days 1-5")
    warnings: list[dict] = Field(default_factory=list, description="IMD colour-coded warnings (Yellow/Orange/Red)")


class Insight(BaseModel):
    variable: Variable
    day: int
    unit: str
    min: float
    max: float
    block_value: float | None
    n_panchayats: int
    text: str


class RainCategory(BaseModel):
    key: str
    label: str


class ValuesVsBlock(BaseModel):
    rain_mm: float | None = None
    tmax: float | None = None
    tmin: float | None = None
    rh: float | None = None
    wind_kmh: float | None = None


class PanchayatDay(BaseModel):
    day: int
    date: str
    weekday: str
    rain_mm: float
    rain_min: float | None
    rain_max: float | None
    rain_prob_2_5mm: float | None
    rain_prob_10mm: float | None
    rain_category: RainCategory
    tmax: float
    tmin: float
    rh: float | None
    wind_kmh: float | None
    confidence: Confidence
    block: ValuesVsBlock
    diff: ValuesVsBlock = Field(description="Panchayat minus block")


class PanchayatInfo(BaseModel):
    id: int
    lgd_code: str
    name: str
    name_te: str | None
    name_hi: str | None
    elevation_m: float | None
    registered_farmers: int | None
    centroid: list[float] | None = Field(None, description="[lon, lat]")
    block: Region
    confidence: Confidence = Field(description="Worst confidence over Days 1-3")


class PanchayatForecast(BaseModel):
    panchayat: PanchayatInfo
    run: RunInfo
    days: list[PanchayatDay]
    alerts: list[AlertOut]
    warnings: list[dict] = Field(default_factory=list, description="IMD colour-coded warnings (Yellow/Orange/Red)")


class AdvisoryGenerateRequest(BaseModel):
    panchayat_id: int
    crop: str = Field(examples=["cotton"])
    stage: str = Field(examples=["square_formation"])
    lang: Lang = "en"


class Advisory(BaseModel):
    id: int | None
    panchayat_id: int
    run_id: int | None = None
    crop: str
    stage: str
    status: Literal["draft", "approved", "sent"]
    items: list[dict]
    edited_text: dict | None = None
    created_at: str | None = None


class AdvisoryPatch(BaseModel):
    edited_text: dict | None = Field(None, description="Officer edits keyed by item id / language")
    items: list[dict] | None = None


class ShareRequest(BaseModel):
    advisory_id: int
    channel: Literal["sms", "whatsapp"]
    language: Lang


class ShareLogEntry(BaseModel):
    id: int
    advisory_id: int
    channel: str
    language: str
    recipients: int
    status: str
    sent_at: str


class RainFeedback(BaseModel):
    panchayat_id: int
    rained: bool
