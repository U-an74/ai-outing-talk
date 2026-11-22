# n8n 등 내부 시스템 전용 API (X-Internal-Key 헤더 인증)

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import INTERNAL_API_KEY
from app.schemas.alert import DispatchRequest
from app.services.dispatch import dispatch_alert, list_due_alerts
from app.services.timeutil import now_utc, to_iso_kst


def verify_internal_key(
    x_internal_key: str | None = Header(default=None, alias="X-Internal-Key"),
):
    """내부 API 키 검증"""

    if not INTERNAL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="INTERNAL_API_KEY가 설정되지 않았습니다.",
        )

    if not x_internal_key or not hmac.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="내부 API 인증에 실패했습니다.",
        )


router = APIRouter(dependencies=[Depends(verify_internal_key)])


@router.get("/alerts/due")
def read_due_alerts():
    """지금 확인해야 하는 알림 목록 (n8n이 10분마다 호출)"""

    now = now_utc()
    try:
        alerts = list_due_alerts(now)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="발송 대상 알림 조회에 실패했습니다.",
        )

    return {
        "now": to_iso_kst(now),
        "count": len(alerts),
        "alerts": alerts,
    }


@router.post("/alerts/{alert_id}/dispatch")
async def dispatch(alert_id: str, body: DispatchRequest):
    """
    알림 발송 API (n8n이 조건을 확인한 뒤 호출)
    AI 문구 생성 → 토큰 확인·갱신 → 카카오톡 나에게 보내기 → 발송 완료 기록
    이미 발송된 알림이면 다시 보내지 않고 status만 반환한다.
    """

    try:
        result = await dispatch_alert(
            user_id=body.user_id,
            alert_id=alert_id,
            weather=body.weather.model_dump() if body.weather else None,
            travel_minutes=body.travel_minutes,
            leave_at=body.leave_at,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"알림 발송에 실패했습니다: {str(e)[:200]}",
        )

    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")

    return result
