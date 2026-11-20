from pydantic import BaseModel
from datetime import datetime


class ReportResponse(BaseModel):
    generated_at: datetime
    report_type: str
    summary: str