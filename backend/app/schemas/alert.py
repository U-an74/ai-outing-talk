#알림 등록 요청 데이터의 형식과 유효성을 검사

from datetime import datetime

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    """외출 알림 등록 요청 데이터 (항목을 직접 입력하는 경우)"""

    departure: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    arrival_at: datetime
    notify_at: datetime
    message: str = Field(..., min_length=1)


class NaturalAlertCreate(BaseModel):
    """자연어 한 문장으로 외출 알림 등록"""

    text: str = Field(..., min_length=2, max_length=300)


class DispatchWeather(BaseModel):
    """n8n이 조회한 발송 시점 날씨"""

    temperature: float | None = None
    precipitation: float | None = None
    precipitation_probability: float | None = None
    summary: str | None = None


class DispatchRequest(BaseModel):
    """n8n → 백엔드 발송 요청"""

    user_id: str = Field(..., min_length=1)
    weather: DispatchWeather | None = None
    travel_minutes: int | None = None
    leave_at: datetime | None = None
