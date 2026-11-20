
# Firestore 데이터 저장 테스트

from app.firebase import db

# 테스트용 알림 데이터
alert_data = {
    "id": "alert_002",
    "user_id": "user_001",
    "departure": "우리 집",
    "destination": "회사",
    "arrival_at": "2026-11-20T09:00:00+09:00",
    "notify_at": "2026-11-20T08:30:00+09:00",
    "condition_type": "weather",
    "condition_value": {
        "type": "rain",
        "operator": "greater_than",
        "value": 0
    },
    "message": "비가 올 예정이에요. 우산을 챙기세요!",
    "status": "pending",
    "created_at": "2026-11-20T08:00:00+09:00",
    "updated_at": "2026-11-20T08:00:00+09:00"
}

# Firestore에 데이터 저장
doc_ref = db.collection("alerts").document(alert_data["id"])
doc_ref.set(alert_data)

print("Firestore 데이터 저장 성공!")
print(f"저장된 문서 ID: {alert_data['id']}")
