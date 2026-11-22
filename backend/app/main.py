#FastAPI 서버 시작점

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.firebase import db #Firestore 연결 테스트용
from app.routers import auth
from app.routers import alerts

app = FastAPI()

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

# CORS 설정
# 로컬 개발용 주소 허용, 추후 Vercel 배포 주소 추가 필요
origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#FastAPI 서버 실행 테스트
@app.get("/")
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
