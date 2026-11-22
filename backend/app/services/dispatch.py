# n8n 예약 발송용 로직: 발송 대상 조회, 발송 처리
#
# 알림 상태 흐름
#   active  → sending → sent      (발송 성공)
#   active  → sending → active    (발송 실패, 다음 주기에 재시도)
#   active  → expired             (도착 시각이 지날 때까지 발송되지 않음)

from datetime import datetime, timedelta

import httpx
from google.cloud import firestore as gcf

from app.config import FRONTEND_URL
from app.firebase import db
from app.services.kakao import send_kakao_message
from app.services.llm import compose_alert_message
from app.services.timeutil import now_utc, parse_iso, to_iso_kst
from app.services.user import get_valid_access_token


# 발송 중(sending) 상태로 이 시간 넘게 멈춰 있으면 실패로 보고 다시 발송 대상에 포함
SENDING_TIMEOUT = timedelta(minutes=5)


def _alert_ref(user_id: str, alert_id: str):
    return (
        db.collection("users")
        .document(str(user_id))
        .collection("alerts")
        .document(alert_id)
    )


def _coord(value) -> dict | None:
    if isinstance(value, dict) and value.get("lat") is not None and value.get("lon") is not None:
        return {"lat": value["lat"], "lon": value["lon"]}
    return None


def serialize_due_alert(user_id: str, alert_id: str, data: dict) -> dict:
    """n8n에 넘길 알림 데이터 (시각은 한국 시각 ISO 문자열)"""

    return {
        "id": alert_id,
        "user_id": str(user_id),
        "departure": data.get("departure"),
        "destination": data.get("destination"),
        "arrival_at": to_iso_kst(parse_iso(data.get("arrival_at"))),
        "notify_at": to_iso_kst(parse_iso(data.get("notify_at"))),
        "notify_mode": data.get("notify_mode") or "fixed",
        "buffer_minutes": data.get("buffer_minutes") or 10,
        "message": data.get("message"),
        "condition": data.get("condition"),
        "departure_coord": _coord(data.get("departure_coord")),
        "destination_coord": _coord(data.get("destination_coord")),
    }


def list_due_alerts(now: datetime | None = None) -> list[dict]:
    """
    지금 확인해야 하는 알림 목록
    - 아직 발송되지 않았고(sent == False)
    - 확인 시작 시각(notify_at)이 지났으며
    - 도착 시각(arrival_at)이 아직 지나지 않은 알림
    도착 시각이 지난 미발송 알림은 expired로 바꾼다.

    사용자 수가 적은 서비스라 별도 색인이 필요 없는 방식(사용자별 순회)으로 조회한다.
    """

    now = now or now_utc()
    due = []

    for user_doc in db.collection("users").stream():
        for alert_doc in user_doc.reference.collection("alerts").stream():
            data = alert_doc.to_dict() or {}

            if data.get("sent") or data.get("status") in ("sent", "expired"):
                continue

            if data.get("status") == "sending":
                sending_at = parse_iso(data.get("sending_at"))
                if sending_at and now - sending_at < SENDING_TIMEOUT:
                    continue

            arrival_at = parse_iso(data.get("arrival_at"))
            if arrival_at and arrival_at < now:
                alert_doc.reference.update({"status": "expired", "updated_at": now})
                continue

            notify_at = parse_iso(data.get("notify_at"))
            if notify_at and notify_at <= now:
                due.append(serialize_due_alert(user_doc.id, alert_doc.id, data))

    due.sort(key=lambda item: item["notify_at"] or "")
    return due


@gcf.transactional
def _claim_alert(transaction, ref, now: datetime) -> str:
    """중복 발송을 막기 위해 트랜잭션으로 알림을 sending 상태로 선점"""

    snapshot = ref.get(transaction=transaction)
    if not snapshot.exists:
        return "not_found"

    data = snapshot.to_dict() or {}
    if data.get("sent") or data.get("status") == "sent":
        return "already_sent"
    if data.get("status") == "expired":
        return "expired"
    if data.get("status") == "sending":
        sending_at = parse_iso(data.get("sending_at"))
        if sending_at and now - sending_at < SENDING_TIMEOUT:
            return "in_progress"

    transaction.update(ref, {"status": "sending", "sending_at": now, "updated_at": now})
    return "claimed"


async def _send_with_refresh(user_id: str, message: str) -> None:
    """토큰을 확인해 발송하고, 401이면 한 번 갱신 후 재시도"""

    access_token = await get_valid_access_token(user_id)
    try:
        await send_kakao_message(access_token, message, FRONTEND_URL)
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 401:
            raise
        access_token = await get_valid_access_token(user_id, force_refresh=True)
        await send_kakao_message(access_token, message, FRONTEND_URL)


async def dispatch_alert(
    user_id: str,
    alert_id: str,
    weather: dict | None,
    travel_minutes: int | None,
    leave_at: datetime | None,
) -> dict:
    """알림 문구를 만들고 카카오톡으로 발송한 뒤 결과를 기록"""

    now = now_utc()
    ref = _alert_ref(user_id, alert_id)

    claim = _claim_alert(db.transaction(), ref, now)
    if claim != "claimed":
        return {"status": claim, "alert_id": alert_id}

    try:
        alert = ref.get().to_dict() or {}
        message, ai_generated = await compose_alert_message(
            alert, weather, travel_minutes, leave_at, now
        )
        await _send_with_refresh(user_id, message)
    except Exception as e:
        ref.update({
            "status": "active",
            "last_error": str(e)[:300],
            "last_error_at": now,
            "updated_at": now,
        })
        raise

    ref.update({
        "status": "sent",
        "sent": True,
        "sent_at": now,
        "final_message": message,
        "ai_generated": ai_generated,
        "weather_at_send": weather,
        "travel_minutes": travel_minutes,
        "leave_at": leave_at,
        "updated_at": now,
    })

    return {
        "status": "sent",
        "alert_id": alert_id,
        "message": message,
        "ai_generated": ai_generated,
    }
