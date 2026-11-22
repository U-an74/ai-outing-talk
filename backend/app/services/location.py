# 장소 이름 → 좌표 변환 (카카오 Local 키워드 검색)
#
# 카카오 디벨로퍼스 앱에서 카카오맵(Local) API가 활성화되어 있어야 한다.
# 검색에 실패해도 알림 등록은 계속 진행하고, 좌표만 비워 둔다.

import httpx

from app.config import KAKAO_REST_API_KEY


KAKAO_LOCAL_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


async def geocode(query: str | None) -> dict | None:
    """장소 이름을 검색해 첫 번째 결과의 좌표 반환"""

    if not query or not KAKAO_REST_API_KEY:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                KAKAO_LOCAL_KEYWORD_URL,
                params={"query": query, "size": 1},
                headers={"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"},
            )
            response.raise_for_status()
            documents = response.json().get("documents", [])
    except (httpx.HTTPError, ValueError):
        return None

    if not documents:
        return None

    place = documents[0]
    try:
        return {
            "lat": float(place["y"]),
            "lon": float(place["x"]),
            "place_name": place.get("place_name") or query,
            "address": place.get("road_address_name") or place.get("address_name") or "",
        }
    except (KeyError, TypeError, ValueError):
        return None
