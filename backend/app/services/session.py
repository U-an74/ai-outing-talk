#로그인 성공 시 인증 토큰 생성, API 요청이 들어올 때 토큰 검증

import hashlib
import hmac
import time

from app.config import APP_SESSION_SECRET


SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7일


def create_session_token(user_id: str) -> str:
    """사용자 ID를 기반으로 서명된 세션 토큰 생성"""

    if not APP_SESSION_SECRET:
        raise ValueError("APP_SESSION_SECRET이 설정되지 않았습니다.")

    issued_at = int(time.time())
    payload = f"{user_id}.{issued_at}"

    signature = hmac.new(
        APP_SESSION_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{payload}.{signature}"


def verify_session_token(token: str) -> str | None:
    """세션 토큰의 서명과 만료 시간을 검증하고 사용자 ID 반환"""

    if not APP_SESSION_SECRET:
        return None

    try:
        user_id, issued_at, signature = token.rsplit(".", 2)
        issued_at = int(issued_at)

        payload = f"{user_id}.{issued_at}"

        expected_signature = hmac.new(
            APP_SESSION_SECRET.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return None

        now = int(time.time())

        if issued_at > now or now - issued_at > SESSION_MAX_AGE:
            return None

        return user_id

    except (ValueError, TypeError):
        return None

#인증되지 않은 요청은 401 오류로 차단, 인증된 요청만 실제 사용자 ID를 받아서 처리
from fastapi import Cookie, HTTPException


def get_current_user_id(
    session_token: str | None = Cookie(default=None),
) -> str:
    """인증 쿠키를 검증하고 로그인 사용자 ID 반환"""

    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="로그인이 필요합니다.",
        )

    user_id = verify_session_token(session_token)

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="인증 세션이 유효하지 않거나 만료되었습니다.",
        )

    return user_id