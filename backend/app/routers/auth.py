# 카카오 로그인 및 OAuth 콜백 처리

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import (
    COOKIE_SECURE,
    FRONTEND_URL,
    KAKAO_REST_API_KEY,
    KAKAO_REDIRECT_URI,
)
from app.services.kakao import get_kakao_token, get_kakao_user_info
from app.services.user import save_kakao_user
from app.services.session import (
    SESSION_MAX_AGE,
    create_session_token,
    get_current_user_id,
)


router = APIRouter()

# 카카오 OAuth 인증 URL
KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"

SESSION_COOKIE = "session_token"


def _frontend_redirect(login_result: str) -> RedirectResponse:
    """로그인 결과를 쿼리로 붙여 프론트엔드로 이동"""

    separator = "&" if "?" in FRONTEND_URL else "?"
    return RedirectResponse(
        url=f"{FRONTEND_URL}{separator}login={login_result}",
        status_code=303,
    )


@router.get("/login")
async def kakao_login():
    """
    카카오 로그인 페이지로 이동
    """

    if not KAKAO_REST_API_KEY or not KAKAO_REDIRECT_URI:
        raise HTTPException(
            status_code=500,
            detail="카카오 OAuth 환경변수가 설정되지 않았습니다."
        )

    params = {
        "response_type": "code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "scope": "talk_message",
    }

    login_url = f"{KAKAO_AUTH_URL}?{urlencode(params)}"

    return RedirectResponse(url=login_url)


@router.get("/callback")
async def kakao_callback(
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """
    카카오 인증 코드를 받아 토큰 발급 → Firestore 저장 → 세션 쿠키 설정 → 프론트로 이동
    """

    # 사용자가 동의를 취소한 경우 등
    if error or not code:
        return _frontend_redirect("fail")

    try:
        token_data = await get_kakao_token(code)
        user_info = await get_kakao_user_info(
            token_data["access_token"]
        )
        save_kakao_user(
            kakao_user_id=user_info["id"],
            token_data=token_data,
        )
    except Exception:
        return _frontend_redirect("fail")

    # 실제 토큰 값은 응답에 노출하지 않고, 서명된 세션 쿠키만 전달
    session_token = create_session_token(
        str(user_info["id"])
    )

    # RedirectResponse에 직접 쿠키를 설정해야 브라우저에 전달됨
    response = _frontend_redirect("success")
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )

    return response


@router.get("/me")
def read_me(user_id: str = Depends(get_current_user_id)):
    """
    현재 로그인한 사용자 확인 (프론트 시작 시 호출)
    로그인하지 않았으면 401
    """

    return {
        "logged_in": True,
        "user_id": user_id,
    }


@router.post("/logout")
def logout():
    """세션 쿠키 삭제"""

    response = JSONResponse({"logged_in": False})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
