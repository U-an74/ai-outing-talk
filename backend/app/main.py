#FastAPI 서버 시작점

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS
from app.firebase import db #Firestore 연결 테스트용
from app.routers import alerts, auth, internal

app = FastAPI(title="AI Outing Talk API")

# 카카오 인증 라우터 등록
app.include_router(
    auth.router,
    prefix="/api/auth/kakao",
    tags=["Kakao Auth"]
)

# 외출 알림 라우터 등록
app.include_router(
    alerts.router,
    prefix="/api/alerts",
    tags=["Alerts"]
)

# n8n 전용 내부 라우터 등록 (X-Internal-Key 인증)
app.include_router(
    internal.router,
    prefix="/api/internal",
    tags=["Internal (n8n)"]
)

# CORS 설정
# 프론트를 백엔드가 함께 서빙하면 같은 주소라 CORS가 필요 없음
# 로컬에서 Live Server(5500)로 띄울 때를 위해 기본값으로 남겨 둠
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#FastAPI 서버 실행 테스트
@app.get("/api")
def read_root():
    return {"message": "AI Outing Talk API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Firestore 연결 테스트용 API
@app.get("/health/firebase")
def firebase_health_check():
    try:
        db.collection("connection_tests").limit(1).get()
        return {"status": "ok", "firebase": "connected"}
    except Exception:
        return {"status": "error", "firebase": "connection_failed"}


# 프론트엔드 정적 파일 서빙
# 백엔드와 같은 주소에서 화면을 제공해 로그인 쿠키, CORS 문제를 없앤다.
# 반드시 모든 API 라우트 등록 뒤(파일 맨 끝)에 두어야 API 경로를 가리지 않는다.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIR, html=True),
        name="frontend",
    )
