
# Firestore 데이터 읽기 테스트

import json
from app.firebase import db

# alerts 컬렉션에서 alert_001 문서 가져오기
doc_ref = db.collection("alerts").document("alert_001")
doc = doc_ref.get()

# 문서 존재 여부 확인
if doc.exists:
    alert_data = doc.to_dict()

    print("Firestore 데이터 조회 성공!")
    print(json.dumps(alert_data, ensure_ascii=False, indent=2))
else:
    print("해당 문서를 찾을 수 없습니다.")
