# Firestore 연결

import firebase_admin
from firebase_admin import credentials, firestore

from .config import FIREBASE_PROJECT_ID, FIREBASE_CREDENTIALS_PATH


# 필수 환경변수 확인
if not FIREBASE_PROJECT_ID or not FIREBASE_CREDENTIALS_PATH:
    raise ValueError("Firebase 환경변수가 설정되지 않았습니다.")


# Firebase Admin SDK 초기화
try:
    firebase_app = firebase_admin.get_app()
except ValueError:
    credential = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_app = firebase_admin.initialize_app(
        credential,
        {"projectId": FIREBASE_PROJECT_ID}
    )


# Firestore 데이터베이스 연결
db = firestore.client(app=firebase_app)
