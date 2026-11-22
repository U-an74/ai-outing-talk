#환경변수 및 설정 관리

import os
from pathlib import Path

from dotenv import load_dotenv


# backend/.env 파일 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# Firebase 설정
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH")


# Kakao OAuth 설정
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

# App session
APP_SESSION_SECRET = os.getenv("APP_SESSION_SECRET")

# 배포(HTTPS) 환경에서는 true로 설정해 쿠키를 HTTPS에서만 전송
COOKIE_SECURE = _env_bool("COOKIE_SECURE", False)

# 로그인 성공 후 돌아갈 프론트엔드 주소
# 프론트를 백엔드가 함께 서빙하므로 기본값은 같은 서버의 첫 화면("/")
FRONTEND_URL = os.getenv("FRONTEND_URL", "/")

# 프론트를 다른 주소에서 띄울 때만 필요 (쉼표로 구분)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500",
    ).split(",")
    if origin.strip()
]

# n8n 등 내부 호출 전용 API 키 (X-Internal-Key 헤더로 전달)
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

# LLM 설정 (OpenAI 호환 Chat Completions 형식)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
