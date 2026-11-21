# 카카오 로그인 및 OAuth 콜백 처리

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.config import KAKAO_REST_API_KEY, KAKAO_REDIRECT_URI
from app.services.kakao import get_kakao_token, get_kakao_user_info
from app.services.user import save_kakao_user


router = APIRouter()

# 카카오 OAuth 인증 URL
KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"


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
    카카오 인증 코드를 받아 Access Token 발급
    """

    if error:
        raise HTTPException(
            status_code=400,
            detail=error_description or error
        )

    if not code:
        raise HTTPException(
            status_code=400,
            detail="카카오 인증 코드가 전달되지 않았습니다."
        )

    try:
        token_data = await get_kakao_token(code)
        user_info = await get_kakao_user_info(
            token_data["access_token"]
        )
        save_kakao_user(
            kakao_user_id=user_info["id"],
            token_data=token_data,
        )

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"카카오 토큰 발급에 실패했습니다: {str(e)}"
        )

    # 실제 토큰 값은 응답에 노출하지 않음
    return {
        "message": "카카오 토큰 발급 성공",
        "kakao_user_id": user_info.get("id"),
        "token_type": token_data.get("token_type"),
        "expires_in": token_data.get("expires_in"),
        "refresh_token_expires_in": token_data.get(
            "refresh_token_expires_in"
        ),
        "scope": token_data.get("scope"),
        "has_access_token": bool(token_data.get("access_token")),
        "has_refresh_token": bool(token_data.get("refresh_token")),
    }
