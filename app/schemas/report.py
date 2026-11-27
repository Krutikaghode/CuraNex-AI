from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    filename: str
    content_type: str
    size_bytes: int
    status: str
    extraction_method: str
    page_count: int
    error: str | None
    created_at: datetime


class ReportDetail(ReportSummary):
    text: str


class ReportCount(BaseModel):
    count: int
