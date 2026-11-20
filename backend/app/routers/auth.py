# 카카오 로그인 및 OAuth 콜백 처리

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.config import KAKAO_REST_API_KEY, KAKAO_REDIRECT_URI
from app.services.kakao import (
    get_kakao_token,
    refresh_kakao_token,
    send_kakao_message,
)


router = APIRouter()

# 로컬 테스트용 토큰 저장 공간
kakao_tokens = {}

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
        kakao_tokens["access_token"] = token_data.get("access_token")
        kakao_tokens["refresh_token"] = token_data.get("refresh_token")

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"카카오 토큰 발급에 실패했습니다: {str(e)}"
        )

    # 실제 토큰 값은 응답에 노출하지 않음
    return {
        "message": "카카오 토큰 발급 성공",
        "token_type": token_data.get("token_type"),
        "expires_in": token_data.get("expires_in"),
        "refresh_token_expires_in": token_data.get(
            "refresh_token_expires_in"
        ),
        "scope": token_data.get("scope"),
        "has_access_token": bool(token_data.get("access_token")),
        "has_refresh_token": bool(token_data.get("refresh_token")),
    }


@router.post("/refresh-test")
async def kakao_refresh_test():
    """
    로컬 테스트용 Refresh Token 갱신
    """

    refresh_token = kakao_tokens.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="저장된 Refresh Token이 없습니다. 먼저 카카오 로그인을 진행하세요."
        )

    try:
        token_data = await refresh_kakao_token(refresh_token)

        kakao_tokens["access_token"] = token_data.get("access_token")

        # 새로운 Refresh Token이 반환된 경우에만 교체
        if token_data.get("refresh_token"):
            kakao_tokens["refresh_token"] = token_data["refresh_token"]

        return {
            "message": "카카오 Access Token 갱신 성공",
            "has_access_token": bool(token_data.get("access_token")),
            "refresh_token_updated": bool(token_data.get("refresh_token")),
            "expires_in": token_data.get("expires_in"),
        }

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"카카오 토큰 갱신 실패: {str(e)}"
        )


@router.post("/message-test")
async def kakao_message_test():
    """
    로컬 테스트용 카카오톡 나에게 보내기
    """

    access_token = kakao_tokens.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="저장된 Access Token이 없습니다. 먼저 카카오 로그인을 진행하세요."
        )

    test_message = "AI 외출톡 테스트 메시지입니다! 카카오톡 알림 발송에 성공했습니다."

    try:
        result = await send_kakao_message(
            access_token=access_token,
            message=test_message,
        )

        return {
            "message": "카카오톡 메시지 발송 성공",
            "result": result,
        }

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"카카오톡 메시지 발송 실패: {str(e)}"
        )
