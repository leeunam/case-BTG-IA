from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class DailyInsight(BaseModel):
    insight_date: date
    generated_at: Optional[datetime]
    status: str          # generated | not_generated | failed | stale
    text: Optional[str]


class VolumeByPeriod(BaseModel):
    period: str
    total_volume: float
    offer_count: int
    ipo_volume: float
    follow_on_volume: float


class RankingItem(BaseModel):
    rank: int
    name: str
    ticker: Optional[str]
    offer_type: str
    total_volume: float
    coordinator: Optional[str]


class IpoVsFollowOn(BaseModel):
    period: str
    ipo_volume: float
    ipo_count: int
    follow_on_volume: float
    follow_on_count: int


class TopNewOffer(BaseModel):
    id: int
    name: str
    ticker: Optional[str]
    offer_type: str
    total_volume: Optional[float]
    coordinator: Optional[str]
    registered_at: Optional[date]
    distribution_rite: Optional[str]


class TopNewOffersResponse(BaseModel):
    ref_date: date
    is_today: bool
    items: list["TopNewOffer"]


class PipelineSourceStatus(BaseModel):
    source_code: str
    source_name: str
    last_run_at: Optional[datetime]
    last_status: Optional[str]
    hours_since_update: Optional[float]
    is_stale: bool


class PipelineHealth(BaseModel):
    sources: list[PipelineSourceStatus]
    failed_today: int
    stale_sources: int
