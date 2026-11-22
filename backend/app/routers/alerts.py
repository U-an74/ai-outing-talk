#네가지 API 요청의 쿠키를 검증하고, 로그인한 사용자의 카카오 ID를 기준으로 Firestore에 접근


import asyncio
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.alert import AlertCreate, NaturalAlertCreate
from app.services.alert import (
    create_alert,
    get_alerts,
    get_alert,
    delete_alert,
)
from app.services.llm import LLMError, parse_outing_text
from app.services.location import geocode
from app.services.session import get_current_user_id
from app.services.timeutil import now_kst


router = APIRouter()

# 출발 알림(departure)은 도착 시각 이 시간 전부터 n8n이 이동 시간을 확인하기 시작
DEPARTURE_LOOKAHEAD = timedelta(minutes=120)


@router.post("/natural")
async def register_natural_alert(
    body: NaturalAlertCreate,
    user_id: str = Depends(get_current_user_id),
):
    """
    자연어 한 문장으로 외출 알림 등록 API
    1) LLM이 문장을 출발지, 도착지, 도착 시각, 조건으로 해석
    2) 카카오 Local로 장소 좌표 검색
    3) Firestore에 저장
    """

    now = now_kst()

    try:
        parsed = await parse_outing_text(body.text, now)
    except LLMError:
        raise HTTPException(
            status_code=502,
            detail="AI가 문장을 해석하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        )

    missing = []
    if not parsed["destination"]:
        missing.append("도착지")
    if not parsed["arrival_at"]:
        missing.append("도착 시각")
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"{', '.join(missing)}을(를) 알 수 없어요. 예) 내일 오전 9시까지 강남역에 가야 해",
        )

    arrival_at = parsed["arrival_at"]
    if arrival_at <= now:
        raise HTTPException(
            status_code=422,
            detail="도착 시각이 이미 지났어요. 앞으로의 일정을 입력해 주세요.",
        )

    # 사용자가 알림 시각을 직접 말했으면 그 시각에(fixed),
    # 아니면 이동 시간으로 출발 시각을 계산해 알림(departure)
    notify_at = parsed["notify_at"]
    if notify_at and notify_at < arrival_at:
        notify_mode = "fixed"
    else:
        notify_mode = "departure"
        notify_at = max(now, arrival_at - DEPARTURE_LOOKAHEAD)

    departure_coord, destination_coord = await asyncio.gather(
        geocode(parsed["departure"]),
        geocode(parsed["destination"]),
    )

    alert_data = {
        "departure": parsed["departure"],
        "destination": parsed["destination"],
        "arrival_at": arrival_at,
        "notify_at": notify_at,
        "notify_mode": notify_mode,
        "condition": parsed["condition"],
        "items_hint": parsed["items_hint"],
        "message": parsed["message"],
        "original_text": body.text,
        "departure_coord": departure_coord,
        "destination_coord": destination_coord,
        "buffer_minutes": 10,
        "ai_parsed": True,
    }

    try:
        saved = create_alert(user_id=user_id, alert_data=alert_data)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="외출 알림 등록에 실패했습니다.",
        )

    return {
        "message": "외출 알림 등록 성공",
        "alert": saved,
    }


@router.post("")
def register_alert(
    alert: AlertCreate,
    user_id: str = Depends(get_current_user_id),
):
    """외출 알림 등록 API"""

    try:
        alert_data = create_alert(
            user_id=user_id,
            alert_data=alert.model_dump(),
        )

        return {
            "message": "외출 알림 등록 성공",
            "alert": alert_data,
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="외출 알림 등록에 실패했습니다.",
        )


@router.get("")
def read_alerts(
    user_id: str = Depends(get_current_user_id),
):
    """외출 알림 목록 조회 API"""

    try:
        alerts = get_alerts(user_id)

        return {
            "message": "외출 알림 목록 조회 성공",
            "count": len(alerts),
            "alerts": alerts,
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="외출 알림 목록 조회에 실패했습니다.",
        )


@router.get("/{alert_id}")
def read_alert_detail(
    alert_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """외출 알림 상세 조회 API"""

    try:
        alert = get_alert(
            user_id=user_id,
            alert_id=alert_id,
        )

        if alert is None:
            raise HTTPException(
                status_code=404,
                detail="해당 외출 알림을 찾을 수 없습니다.",
            )

        return {
            "message": "외출 알림 상세 조회 성공",
            "alert": alert,
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="외출 알림 상세 조회에 실패했습니다.",
        )


@router.delete("/{alert_id}")
def remove_alert(
    alert_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """외출 알림 삭제 API"""

    try:
        deleted = delete_alert(
            user_id=user_id,
            alert_id=alert_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="삭제할 외출 알림을 찾을 수 없습니다.",
            )

        return {
            "message": "외출 알림 삭제 성공",
            "alert_id": alert_id,
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="외출 알림 삭제에 실패했습니다.",
        )
