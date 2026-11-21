#카카오 인증 코드 교환, 토큰 발급

import json
import httpx

from app.config import (
    KAKAO_REST_API_KEY,
    KAKAO_CLIENT_SECRET,
    KAKAO_REDIRECT_URI,
)


# 카카오 OAuth 토큰 발급 URL
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"

# 카카오톡 나에게 보내기 API URL
KAKAO_MESSAGE_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
async def get_kakao_token(code: str):
    """
    카카오 인증 코드를 Access Token으로 교환
    """

    if not KAKAO_REST_API_KEY or not KAKAO_CLIENT_SECRET:
        raise ValueError("카카오 OAuth 환경변수가 설정되지 않았습니다.")


    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
        "client_secret": KAKAO_CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            KAKAO_TOKEN_URL,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
        )

        response.raise_for_status()

        return response.json()



async def refresh_kakao_token(refresh_token: str):
    """
    Refresh Token으로 새로운 Access Token 발급
    """

    if not KAKAO_REST_API_KEY or not KAKAO_CLIENT_SECRET:
        raise ValueError("카카오 OAuth 환경변수가 설정되지 않았습니다.")

    if not refresh_token:
        raise ValueError("Refresh Token이 전달되지 않았습니다.")

    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": refresh_token,
        "client_secret": KAKAO_CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            KAKAO_TOKEN_URL,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
        )

        response.raise_for_status()

        return response.json()


async def send_kakao_message(access_token: str, message: str):
    """
    카카오톡 나와의 채팅으로 메시지 발송
    """

    if not access_token:
        raise ValueError("Access Token이 전달되지 않았습니다.")

    if not message:
        raise ValueError("메시지 내용이 비어 있습니다.")

    template_object = {
        "object_type": "text",
        "text": message,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com",
        },
        "button_title": "확인하기",
    }

    data = {
        "template_object": json.dumps(
            template_object,
            ensure_ascii=False
        )
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            KAKAO_MESSAGE_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            },
        )

        response.raise_for_status()

        return response.json()
