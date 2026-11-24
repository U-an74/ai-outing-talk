#사용자별 외출 알림 API 4종 구현


from datetime import datetime, timezone
from uuid import uuid4

from app.firebase import db
from app.services.timeutil import ensure_aware

#Create
def create_alert(user_id: str, alert_data: dict):
    """
    사용자별 외출 알림을 Firestore에 저장
    시간대 없는 시각은 한국 시각으로 보정하고, 발송 상태 기본값을 넣는다.
    """

    alert_id = str(uuid4())
    now = datetime.now(timezone.utc)

    for key in ("arrival_at", "notify_at"):
        if isinstance(alert_data.get(key), datetime):
            alert_data[key] = ensure_aware(alert_data[key])

    data = {
        "kind": "trip",
        "repeat": "none",
        "notify_mode": "fixed",
        "condition": None,
        "buffer_minutes": 10,
        **alert_data,
        "alert_id": alert_id,
        "user_id": user_id,
        "status": "active",
        "sent": False,
        "created_at": now,
        "updated_at": now,
    }

    db.collection("users").document(user_id).collection(
        "alerts"
    ).document(alert_id).set(data)

    return data

#Read
def get_alerts(user_id: str):
    """
    사용자별 외출 알림 목록 조회
    """

    alerts_ref = (
        db.collection("users")
        .document(user_id)
        .collection("alerts")
    )

    docs = alerts_ref.order_by(
        "created_at",
        direction="DESCENDING"
    ).stream()

    return [
        doc.to_dict()
        for doc in docs
    ]

#Read detail
def get_alert(user_id: str, alert_id: str):
    """
    사용자별 특정 외출 알림 상세 조회
    """

    doc_ref = (
        db.collection("users")
        .document(user_id)
        .collection("alerts")
        .document(alert_id)
    )

    doc = doc_ref.get()

    if not doc.exists:
        return None

    return doc.to_dict()

#Delete
def delete_alert(user_id: str, alert_id: str):
    """
    사용자별 외출 알림 삭제
    """

    doc_ref = (
        db.collection("users")
        .document(user_id)
        .collection("alerts")
        .document(alert_id)
    )

    doc = doc_ref.get()

    if not doc.exists:
        return False

    doc_ref.delete()

    return True