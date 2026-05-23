from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ReportJob(BaseModel):
    job_id: str
    offer_id: Optional[int]
    status: str          # queued | processing | completed | failed
    progress: int = 0
    download_url: Optional[str]
    error: Optional[str]
    created_at: datetime
