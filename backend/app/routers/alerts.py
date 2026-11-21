#네가지 API 요청의 쿠키를 검증하고, 로그인한 사용자의 카카오 ID를 기준으로 Firestore에 접근


from fastapi import APIRouter, Depends, HTTPException

from app.schemas.alert import AlertCreate
from app.services.alert import (
    create_alert,
    get_alerts,
    get_alert,
    delete_alert,
)
from app.services.session import get_current_user_id


router = APIRouter()


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
