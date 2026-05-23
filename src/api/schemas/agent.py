from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ConversationItem(BaseModel):
    id: str
    thread_id: str
    title: Optional[str]
    created_at: datetime
    last_message_at: datetime


class MessageRequest(BaseModel):
    thread_id: str
    message: str


class DocumentItem(BaseModel):
    id: int
    offer_id: Optional[int]
    type: str
    title: str
    source_url: Optional[str]
    download_url: Optional[str]
    available: bool
    extraction_status: str
