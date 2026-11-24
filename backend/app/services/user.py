from datetime import datetime, timedelta, timezone

from app.firebase import db
from app.services.kakao import refresh_kakao_token


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


def get_user(user_id: str) -> dict | None:
    """Firestore에서 사용자 정보(토큰 포함) 조회"""

    doc = db.collection("users").document(str(user_id)).get()
    if not doc.exists:
        return None
    return doc.to_dict()


def update_user_tokens(user_id: str, token_data: dict) -> dict:
    """
    토큰 갱신 결과를 Firestore에 반영
    카카오는 Refresh Token 만료가 가까울 때만 새 Refresh Token을 함께 준다.
    """

    now = datetime.now(timezone.utc)
    update = {
        "access_token": token_data.get("access_token"),
        "access_token_expires_at": now + timedelta(
            seconds=token_data.get("expires_in", 0)
        ),
        "updated_at": now,
    }

    if token_data.get("refresh_token"):
        update["refresh_token"] = token_data["refresh_token"]
        update["refresh_token_expires_at"] = now + timedelta(
            seconds=token_data.get("refresh_token_expires_in", 0)
        )

    db.collection("users").document(str(user_id)).set(update, merge=True)
    return update


async def refresh_and_save_token(user_id: str, refresh_token: str) -> str:
    """Refresh Token으로 Access Token을 갱신하고 저장한 뒤 새 Access Token 반환"""

    token_data = await refresh_kakao_token(refresh_token)
    update_user_tokens(user_id, token_data)
    return token_data["access_token"]


async def get_valid_access_token(user_id: str, force_refresh: bool = False) -> str:
    """
    발송에 쓸 수 있는 Access Token 반환
    만료 5분 전이거나 force_refresh면 갱신한다.
    """

    user = get_user(user_id)
    if not user:
        raise ValueError("사용자 정보를 찾을 수 없습니다.")

    refresh_token = user.get("refresh_token")
    access_token = user.get("access_token")
    expires_at = user.get("access_token_expires_at")
    now = datetime.now(timezone.utc)

    needs_refresh = (
        force_refresh
        or not access_token
        or expires_at is None
        or expires_at <= now + timedelta(minutes=5)
    )

    if not needs_refresh:
        return access_token

    if not refresh_token:
        raise ValueError("Refresh Token이 없습니다. 다시 로그인해야 합니다.")

    return await refresh_and_save_token(user_id, refresh_token)
