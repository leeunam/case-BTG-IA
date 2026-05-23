from datetime import date
from typing import Optional
from pydantic import BaseModel


class MacroKpi(BaseModel):
    code: str
    label: str
    value: Optional[float]
    display_value: str
    unit: str
    metric_date: Optional[date]
    source: str


class IpcaMonthlyPoint(BaseModel):
    month: str       # "YYYY-MM"
    value: float


class PlayerItem(BaseModel):
    coordinator: str
    total_offers: int
    total_volume: float
    unique_funds: int
    share_qty_pct: float
    share_vol_pct: float
    last_offer_date: Optional[date]


class TopPlayerInsight(BaseModel):
    coordinator: str
    share_vol_pct: float
    offer_count: int
    dominant_offer_type: str
    status: str          # generated | not_generated
    text: Optional[str]


class OffersByCoordinator(BaseModel):
    coordinator: str
    count: int
    volume: float


class FundVolume(BaseModel):
    name: str
    ticker: Optional[str]
    total_volume: float
