from datetime import datetime, timedelta, timezone

from app.firebase import db


def save_kakao_user(
    kakao_user_id: int,
    token_data: dict,
):
    """
    카카오 사용자 정보와 토큰을 Firestore에 저장
    """

    now = datetime.now(timezone.utc)

    user_data = {
        "kakao_user_id": kakao_user_id,
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "access_token_expires_at": now + timedelta(
            seconds=token_data.get("expires_in", 0)
        ),
        "refresh_token_expires_at": now + timedelta(
            seconds=token_data.get("refresh_token_expires_in", 0)
        ),
        "updated_at": now,
    }

    db.collection("users").document(
        str(kakao_user_id)
    ).set(user_data, merge=True)

    return user_data