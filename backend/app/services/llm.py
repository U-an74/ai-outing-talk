# LLM 호출: 외출 계획 문장 해석, 알림 문구 생성
#
# OpenAI 호환 Chat Completions 형식(POST {LLM_BASE_URL}/chat/completions)을 사용한다.
# 다른 형식의 LLM API를 쓰게 되면 chat() 함수 하나만 바꾸면 된다.

import json
import re
from datetime import datetime

import httpx

from app.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)
from app.services.timeutil import describe_now, format_hm, parse_iso


AI_LABEL = "(AI가 작성한 메시지)"

# 카카오톡 텍스트 템플릿 최대 길이는 200자
KAKAO_TEXT_LIMIT = 200


class LLMError(Exception):
    """LLM 호출 또는 응답 해석 실패"""


async def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 500) -> str:
    """LLM에 대화를 보내고 응답 텍스트를 반환"""

    if not LLM_API_KEY or not LLM_MODEL:
        raise LLMError("LLM 환경변수(LLM_API_KEY, LLM_MODEL)가 설정되지 않았습니다.")

    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            )
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
        raise LLMError(f"LLM 호출 실패: {e}") from e


def extract_json(text: str) -> dict:
    """응답에서 JSON 객체만 꺼내기 (```json 코드블록이나 앞뒤 설명이 붙어도 처리)"""

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise LLMError("LLM 응답에서 JSON을 찾지 못했습니다.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM 응답 JSON 해석 실패: {e}") from e


# ---------------------------------------------------------------------------
# 1. 외출 계획 문장 → 구조화된 알림 데이터
# ---------------------------------------------------------------------------

PARSE_SYSTEM_PROMPT = """너는 사용자의 외출 관련 문장을 알림 데이터(JSON)로 바꾸는 도우미다.
현재 시각: {now}

알림은 두 종류다.
- "trip": 어디로 언제까지 가야 하는 약속·외출 (도착지와 도착 시각이 있음)
  예) "내일 2시까지 강남역 가야 해", "금요일 저녁 7시 홍대 약속"
- "reminder": 정해진 시각에 받는 알림 (반복 가능, 날씨 조건 가능)
  예) "매일 아침 7시 반에 영하면 패딩 챙기라고 알려줘", "내일 8시에 비 오면 우산 챙기라고 해줘"

아래 형식의 JSON 객체 하나만 출력한다. 설명, 코드블록 표시는 쓰지 않는다.
{{
  "kind": "trip" 또는 "reminder",
  "departure": 출발지 이름 또는 null,
  "destination": 도착지 이름 또는 null,
  "arrival_at": 도착해야 하는 시각, "+09:00"이 붙은 ISO 8601 문자열 또는 null,
  "send_at": 알림 받을 시각, "+09:00"이 붙은 ISO 8601 문자열 또는 null,
  "repeat": "none" | "daily" | "weekdays",
  "location": 날씨를 확인할 장소 이름 또는 null,
  "condition": {{"type": "temperature" | "precipitation", "op": "<" | "<=" | ">" | ">=", "value": 숫자}} 또는 null,
  "items_hint": 챙길 준비물, 없으면 "",
  "message": 사용자 요청을 한 문장으로 정리한 문자열
}}

규칙:
- "내일", "모레", "다음 주 월요일" 같은 표현은 현재 시각을 기준으로 실제 날짜로 바꾼다.
- 오전/오후 표시가 없으면 상식적으로 판단한다. (예: "3시 약속" → 오후 3시, "아침 7시" → 오전 7시)
- 날짜 없이 시각만 말했는데 그 시각이 이미 지났으면 다음 날로 본다.
- reminder는 send_at이 꼭 있어야 한다. trip의 send_at은 사용자가 알림 시각을 직접 말한 경우에만 쓴다.
- "매일" → repeat = "daily", "평일마다", "출근하는 날마다" → repeat = "weekdays", 그 외 → "none"
- 장소 이름은 지도에서 검색할 수 있게 사용자가 쓴 그대로 짧게 적는다. (예: "강남역", "회사")
- reminder에서 장소를 말하지 않았으면 location은 null로 둔다. trip이면 location은 도착지와 같게 둔다.
- 조건 변환
  - "영하면", "0도보다 추우면" → {{"type": "temperature", "op": "<", "value": 0}}
  - "5도 이하면" → {{"type": "temperature", "op": "<=", "value": 5}}
  - "30도 넘으면" → {{"type": "temperature", "op": ">", "value": 30}}
  - "비 오면", "눈 오면", "우산" → {{"type": "precipitation", "op": ">=", "value": 50}} (강수확률 %)
- 알 수 없는 값은 지어내지 말고 null로 둔다.
"""

VALID_OPS = ("<", "<=", ">", ">=")


def normalize_condition(raw) -> dict | None:
    """
    조건을 {"type", "op", "value"} 형식으로 통일
    - type: "temperature"(기온, 도) 또는 "precipitation"(강수확률, %)
    - 예전 형식(rain, temp_below, temp_above)도 받아서 바꿔 준다.
    """

    if not isinstance(raw, dict):
        return None

    ctype = str(raw.get("type") or "").strip().lower()
    op = raw.get("op")
    value = raw.get("value")

    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None

    if ctype in ("rain", "snow", "precipitation", "precipitation_probability"):
        return {
            "type": "precipitation",
            "op": op if op in VALID_OPS else ">=",
            "value": value if value is not None else 50.0,
        }

    if ctype == "temp_below":
        return {"type": "temperature", "op": "<", "value": value if value is not None else 0.0}

    if ctype == "temp_above":
        return {"type": "temperature", "op": ">", "value": value if value is not None else 30.0}

    if ctype in ("temperature", "temp"):
        if op not in VALID_OPS or value is None:
            return None
        return {"type": "temperature", "op": op, "value": value}

    return None


def _clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


async def parse_outing_text(text: str, now: datetime) -> dict:
    """외출 관련 문장을 구조화된 dict로 변환"""

    messages = [
        {"role": "system", "content": PARSE_SYSTEM_PROMPT.format(now=describe_now(now))},
        {"role": "user", "content": text},
    ]
    raw = await chat(messages, temperature=0.0)
    data = extract_json(raw)

    destination = _clean(data.get("destination"))
    arrival_at = parse_iso(data.get("arrival_at"))
    send_at = parse_iso(data.get("send_at") or data.get("notify_at"))

    kind = data.get("kind")
    if kind not in ("trip", "reminder"):
        kind = "trip" if destination and arrival_at else "reminder"

    repeat = data.get("repeat")
    if repeat not in ("none", "daily", "weekdays"):
        repeat = "none"

    return {
        "kind": kind,
        "departure": _clean(data.get("departure")),
        "destination": destination,
        "arrival_at": arrival_at,
        "send_at": send_at,
        "repeat": repeat,
        "location": _clean(data.get("location")) or (destination if kind == "trip" else None),
        "condition": normalize_condition(data.get("condition")),
        "items_hint": _clean(data.get("items_hint")) or "",
        "message": _clean(data.get("message")) or text.strip(),
    }


# ---------------------------------------------------------------------------
# 2. 발송 시점 알림 문구 생성
# ---------------------------------------------------------------------------

COMPOSE_SYSTEM_PROMPT = """너는 외출 알림을 카카오톡으로 보내는 비서다.
주어진 정보만 사용해 친근한 존댓말 메시지를 쓴다.

규칙:
- 2~3문장, 120자 이내
- 약속·외출 알림이면 출발 권장 시각을 반드시 포함한다. 이미 지났으면 지금 바로 출발하라고 알린다.
- 정해진 시각 알림이면 사용자 요청 내용을 날씨와 함께 전한다.
- 강수확률이 50% 이상이거나 비/눈이 오면 우산을 챙기라고 한다.
- 기온이 5도 이하이면 따뜻한 옷을, 28도 이상이면 더위 대비를 권한다.
- 사용자가 말한 준비물이 있으면 함께 알려준다.
- 주어지지 않은 정보(교통 상황, 정확하지 않은 수치)는 지어내지 않는다.
- 이모지, 해시태그는 쓰지 않는다. 메시지 본문만 출력한다.
"""


def _weather_line(weather: dict | None) -> str:
    if not weather:
        return "날씨 정보 없음"
    parts = []
    if weather.get("summary"):
        parts.append(str(weather["summary"]))
    if weather.get("temperature") is not None:
        parts.append(f"기온 {weather['temperature']}도")
    if weather.get("precipitation_probability") is not None:
        parts.append(f"강수확률 {weather['precipitation_probability']}%")
    return ", ".join(parts) or "날씨 정보 없음"


def fallback_message(
    alert: dict,
    weather: dict | None,
    travel_minutes: int | None,
    leave_at: datetime | None,
) -> str:
    """LLM을 쓸 수 없을 때 보내는 기본 문구"""

    lines = []
    if alert.get("kind") == "reminder":
        lines.append(f"요청하신 알림입니다: {alert.get('message') or ''}".strip())
    else:
        destination = alert.get("destination") or "목적지"
        if leave_at:
            lines.append(f"{destination}까지 {format_hm(leave_at)}에 출발하세요.")
        else:
            arrival = parse_iso(alert.get("arrival_at"))
            when = f" {format_hm(arrival)}" if arrival else ""
            lines.append(f"{destination}{when} 약속 알림입니다.")
    if travel_minutes is not None:
        lines.append(f"예상 이동 시간은 약 {travel_minutes}분입니다.")
    if weather:
        lines.append(f"현재 날씨: {_weather_line(weather)}.")
        prob = weather.get("precipitation_probability")
        if prob is not None and prob >= 50:
            lines.append("우산을 챙기세요.")
    if alert.get("items_hint"):
        lines.append(f"준비물: {alert['items_hint']}")
    return " ".join(lines)


def finalize_message(body: str) -> str:
    """AI 작성 표시를 붙이고 카카오 글자 수 제한에 맞추기"""

    body = body.strip()
    room = KAKAO_TEXT_LIMIT - len(AI_LABEL) - 1
    if len(body) > room:
        body = body[: room - 1].rstrip() + "…"
    return f"{body}\n{AI_LABEL}"


async def compose_alert_message(
    alert: dict,
    weather: dict | None,
    travel_minutes: int | None,
    leave_at: datetime | None,
    now: datetime,
) -> tuple[str, bool]:
    """
    발송할 알림 문구 생성
    반환값: (문구, AI 생성 여부). LLM 실패 시 기본 문구로 대체한다.
    """

    arrival = parse_iso(alert.get("arrival_at"))
    kind_text = "정해진 시각 알림" if alert.get("kind") == "reminder" else "약속·외출 출발 알림"
    facts = [
        f"현재 시각: {describe_now(now)}",
        f"알림 종류: {kind_text}",
        f"사용자 요청: {alert.get('message') or alert.get('original_text') or ''}",
        f"출발지: {alert.get('departure') or '알 수 없음'}",
        f"도착지: {alert.get('destination') or '알 수 없음'}",
        f"도착 시각: {format_hm(arrival) or '알 수 없음'}",
        f"예상 이동 시간: {f'{travel_minutes}분' if travel_minutes is not None else '알 수 없음'}",
        f"출발 권장 시각: {format_hm(leave_at) or '알 수 없음'}",
        f"날씨: {_weather_line(weather)}",
        f"사용자가 말한 준비물: {alert.get('items_hint') or '없음'}",
    ]

    try:
        body = await chat(
            [
                {"role": "system", "content": COMPOSE_SYSTEM_PROMPT},
                {"role": "user", "content": "\n".join(facts)},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        if not body:
            raise LLMError("빈 응답")
        return finalize_message(body), True
    except LLMError:
        return finalize_message(fallback_message(alert, weather, travel_minutes, leave_at)), False
