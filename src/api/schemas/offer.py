from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class OfferItem(BaseModel):
    id: int
    cvm_registration: Optional[str]
    name: str
    ticker: Optional[str]
    offer_type: str          # "ipo" | "follow_on"
    status: str
    total_volume: Optional[float]
    fund_type: Optional[str]
    segment: Optional[str]
    manager: Optional[str]
    administrator: Optional[str]
    lead_coordinator: Optional[str]
    participants: list[str]
    distribution_rite: Optional[str]
    financial_terms_available: bool
    start_date: Optional[date]
    registered_at: Optional[date]
    updated_at: Optional[datetime]


class OfferList(BaseModel):
    items: list[OfferItem]
    page: int
    page_size: int
    total_count: int


class IndicatorData(BaseModel):
    dy_12m: Optional[float]
    dy_6m: Optional[float]
    pvp: Optional[float]
    price: Optional[float]
    pl_total: Optional[float]
    vacancy_rate: Optional[float]
    volume_daily: Optional[float]
    nav_per_unit: Optional[float]
    monthly_return: Optional[float]
    unit_price: Optional[float]          # offer price (from CVM)
    market_price: Optional[float]        # secondary market price
    spread_pct: Optional[float]          # (unit_price - market_price) / market_price * 100
    snapshot_date: Optional[date]
    source: str = "Fundamentus"


class CompareOffer(BaseModel):
    offer: OfferItem
    indicators: IndicatorData
