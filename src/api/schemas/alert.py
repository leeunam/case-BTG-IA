from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AlertItem(BaseModel):
    id: int
    type: str
    offer_id: Optional[int]
    offer_name: Optional[str]
    ticker: Optional[str]
    offer_type: Optional[str]   # "ipo" | "follow_on"
    seen: bool
    created_at: datetime
    detail: str


class AlertList(BaseModel):
    items: list[AlertItem]
    page: int
    page_size: int
    total_count: int


class AlertSummary(BaseModel):
    total: int
    seen: int
    unseen: int
