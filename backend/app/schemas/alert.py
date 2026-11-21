#알림 등록 요청 데이터의 형식과 유효성을 검사

from datetime import datetime

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    """외출 알림 등록 요청 데이터"""

    departure: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    arrival_at: datetime
    notify_at: datetime
    message: str = Field(..., min_length=1)
