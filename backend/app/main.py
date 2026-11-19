#FastAPI 서버 시작점

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS 설정
# 우선 로컬 개발용 주소만 허용한 상태, 차후 Vercel 배포 주소 추가 요망
origins = [
    "http://127.0.0.1:5500",
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