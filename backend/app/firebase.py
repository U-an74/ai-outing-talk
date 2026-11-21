# firestore 연결

import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv


# .env 파일 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# 환경변수 불러오기
PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH")


# 필수 환경변수 확인
if not PROJECT_ID or not CREDENTIALS_PATH:
    raise ValueError("Firebase 환경변수가 설정되지 않았습니다.")


# Firebase Admin SDK 초기화
try:
    firebase_app = firebase_admin.get_app()
except ValueError:
    credential = credentials.Certificate(CREDENTIALS_PATH)
    firebase_app = firebase_admin.initialize_app(
        credential,
        {"projectId": PROJECT_ID}
    )


# Firestore 데이터베이스 연결
db = firestore.client(app=firebase_app)
