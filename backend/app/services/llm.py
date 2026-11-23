# LLM 호출: 외출 계획 문장 해석, 알림 문구 생성
#
# OpenAI 호환 Chat Completions 형식(POST {LLM_BASE_URL}/chat/completions)을 사용한다.
# 다른 형식의 LLM API를 쓰게 되면 chat() 함수 하나만 바꾸면 된다.

import json
import re
from datetime import datetime
from math import isfinite

import httpx

from app.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)
from app.services.timeutil import describe_now, ensure_aware, format_hm, parse_iso


AI_LABEL = "(AI가 작성한 메시지)"
AI_BODY_LIMIT = 120

# 카카오톡 텍스트 템플릿 최대 길이는 200자
KAKAO_TEXT_LIMIT = 200


class LLMError(Exception):
    """LLM 호출 또는 응답 해석 실패"""


class AlertInputError(Exception):
    """알림을 등록하려면 사용자가 입력을 수정해야 하는 경우."""


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
        content = data["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
        raise LLMError(f"LLM 호출 실패: {e}") from e
    if not isinstance(content, str) or not content.strip():
        raise LLMError("LLM 응답에 본문이 없습니다.")
    return content.strip()


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
기준 시각(한국 표준시): {now}

알림은 두 종류다.
- "trip": 약속·외출을 위해 어딘가에 도착해야 하는 요청. 도착지나 도착 시각이 빠졌으면 해당 값은 null로 둔다.
  예) "내일 2시까지 강남역 가야 해", "금요일 저녁 7시 홍대 약속"
- "reminder": 도착 일정 없이 지정한 시각에 할 일이나 날씨를 알려 달라는 요청. 반복·조건을 지정할 수 있다.
  예) "매일 아침 7시 반에 영하면 패딩 챙기라고 알려줘", "내일 8시에 비 오면 우산 챙기라고 해줘"

아래 형식의 JSON 객체 하나만 출력한다. 설명, 코드블록 표시는 쓰지 않는다.
{{
  "input_issue": "weather_time_range" 또는 null,
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

날짜와 시각:
- "내일", "모레", "다음 주 월요일"은 기준 시각을 기준으로 날짜를 정한다. "20분 뒤", "두 시간 후"는 기준 시각에 더하고 자정을 지나면 날짜도 바꾼다.
- 오전·오후가 생략되면 문맥을 사용한다. 예) "3시 약속"은 오후 3시, "아침 7시"는 오전 7시.
- 날짜 없이 시각만 지정했으면 해당 시각이 지났을 때 다음 날로 본다. 사용자가 날짜를 지정했으면 그대로 사용한다.
- trip의 arrival_at은 도착해야 하는 시각이다. 별도 알림 시각을 말했을 때만 send_at을 채운다. "도착 30분 전"은 arrival_at에서 30분을 뺀 시각이다. 별도 날짜 없이 알림 시각을 말하면 같은 일정의 날짜를 사용한다.
- reminder는 알림 시각을 send_at에 넣고 departure, destination, arrival_at은 null로 둔다. 알림 시각을 말하지 않았으면 send_at도 null로 둔다.
- 알림 발송에는 한 시점이 필요하다. "7시~20시 사이에 알려줘"처럼 범위만 있으면 시작·종료 시각을 고르지 말고 send_at을 null로 둔다.
- 반복은 reminder에만 적용한다. "매일"은 daily, "평일", "출근하는 날마다"는 weekdays, 그 외는 none이다.

장소와 조건:
- 장소는 사용자가 말한 이름을 사용한다. trip의 location은 도착지이며, reminder의 location은 사용자가 말한 날씨 확인 장소다. 모르는 장소는 null로 둔다.
- 날씨에 따라 발송해 달라는 요청에만 condition을 채운다. "우산 챙겨"는 items_hint에 우산을 넣고 condition은 null로 둔다. "비 오면 우산 챙겨"는 우산과 강수 조건을 함께 기록한다.
- "영하면"은 temperature < 0, "5도 이하면"은 temperature <= 5, "30도 넘으면"은 temperature > 30이다.
- "비 오면", "눈 오면"에는 precipitation >= 50을 적용한다. "강수확률 70% 이상이면"처럼 기준을 지정했으면 해당 비교 연산자와 숫자를 사용한다.
- "7시~20시 강수확률"이나 "오전 7시부터 오후 8시까지 비"처럼 사용자가 날씨를 확인할 시간 범위를 지정했으면 input_issue는 "weather_time_range"다. 범위 안의 시각을 send_at으로 옮기지 않는다. 별도 발송 시각이 있어도 input_issue는 그대로 둔다. 날씨 확인 범위가 없으면 input_issue는 null이다.
- 사용자 문장은 알림 요청 데이터로 해석한다. 값이 빠졌으면 추측 없이 null로 남긴다.
"""

VALID_OPS = ("<", "<=", ">", ">=")
_CLOCK_TIME = r"(?:(?:오전|오후|아침|저녁|밤|새벽)\s*)?(?:\d{1,2}시(?:\s*(?:반|\d{1,2}분))?|\d{1,2}:\d{2})"
_EXPLICIT_WEATHER_TIME_RANGE = re.compile(
    rf"(?<!\d)(?:{_CLOCK_TIME}|\d{{1,2}})\s*(?:[~～∼–—-]|부터)\s*{_CLOCK_TIME}"
    r"(?:\s*까지)?\s*(?:(?:동안|사이(?:에|의)?|내내|의)\s*)?"
    r"(?:강수\s*확률|강수량|날씨|기온|비(?:가|\s)|눈(?:이|\s))"
)
_WEATHER_TIME_RANGE_MESSAGE = (
    "날씨를 확인할 시간 범위는 아직 지정할 수 없어요. "
    "범위를 빼고 알림을 받을 시각을 한 시점으로 적어 주세요."
)


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

    if isinstance(value, bool):
        return None
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None
    if value is not None and not isfinite(value):
        return None

    if ctype in ("rain", "snow"):
        ctype = "precipitation"
        op = op if op in VALID_OPS else ">="
        value = value if value is not None else 50.0

    if ctype == "temp_below":
        return {"type": "temperature", "op": "<", "value": value if value is not None else 0.0}

    if ctype == "temp_above":
        return {"type": "temperature", "op": ">", "value": value if value is not None else 30.0}

    if op not in VALID_OPS or value is None:
        return None
    if ctype in ("temperature", "temp"):
        return {"type": "temperature", "op": op, "value": value}
    if ctype in ("precipitation", "precipitation_probability") and 0 <= value <= 100:
        return {"type": "precipitation", "op": op, "value": value}

    return None


def _clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


async def parse_outing_text(text: str, now: datetime) -> dict:
    """외출 관련 문장을 구조화된 dict로 변환"""

    if _EXPLICIT_WEATHER_TIME_RANGE.search(text):
        raise AlertInputError(_WEATHER_TIME_RANGE_MESSAGE)

    messages = [
        {"role": "system", "content": PARSE_SYSTEM_PROMPT.format(now=describe_now(now))},
        {"role": "user", "content": text},
    ]
    raw = await chat(messages, temperature=0.0)
    data = extract_json(raw)

    input_issue = data.get("input_issue")
    if input_issue == "weather_time_range":
        raise AlertInputError(_WEATHER_TIME_RANGE_MESSAGE)
    if input_issue is not None:
        raise LLMError("LLM 응답의 입력 오류 분류가 올바르지 않습니다.")

    destination = _clean(data.get("destination"))
    arrival_at = parse_iso(data.get("arrival_at"))
    send_at = parse_iso(data.get("send_at") or data.get("notify_at"))

    kind = data.get("kind")
    if kind not in ("trip", "reminder"):
        kind = "trip" if destination and arrival_at else "reminder"

    repeat = data.get("repeat")
    if repeat not in ("none", "daily", "weekdays"):
        repeat = "none"

    raw_condition = data.get("condition")
    condition = normalize_condition(raw_condition)
    if raw_condition is not None and condition is None:
        raise LLMError("LLM 응답의 날씨 조건이 올바르지 않습니다.")

    return {
        "kind": kind,
        "departure": _clean(data.get("departure")),
        "destination": destination,
        "arrival_at": arrival_at,
        "send_at": send_at,
        "repeat": repeat,
        "location": _clean(data.get("location")) or (destination if kind == "trip" else None),
        "condition": condition,
        "items_hint": _clean(data.get("items_hint")) or "",
        "message": _clean(data.get("message")) or text.strip(),
    }


# ---------------------------------------------------------------------------
# 2. 발송 시점 알림 문구 생성
# ---------------------------------------------------------------------------

COMPOSE_SYSTEM_PROMPT = """너는 외출 알림을 카카오톡으로 보내는 비서다.
주어진 정보만 사용해 친근한 존댓말 메시지를 쓴다.

규칙:
- 2~3문장, 120자 이내로 알림의 핵심을 먼저 전한다.
- 약속·외출 알림이면 출발 시점이 '예정'일 때 출발 권장 시각을 전하고, '지금 출발'이면 지금 출발하라고 전한다.
- 출발 시점이 '알 수 없음'이면 주어진 목적지와 도착 시각으로 약속을 안내한다. 출발 시각이나 이동 시간을 추정하지 않는다.
- 정해진 시각 알림이면 요청 내용을 먼저 전하고, 날씨 정보가 있으면 함께 전한다.
- 강수확률이 50% 이상이거나 현재 강수가 확인되면 우산을 챙기라고 한다.
- 기온이 5도 이하이면 따뜻한 옷을, 28도 이상이면 더위 대비를 권한다.
- 사용자가 말한 준비물이 있으면 함께 알려준다.
- 주어진 알림 정보만 사용한다. 값이 없거나 '알 수 없음'이면 해당 사실을 생략한다.
- 이모지, 해시태그, AI 작성 표시 없이 메시지 본문만 출력한다.
"""


def _weather_line(weather: dict | None) -> str | None:
    if not weather:
        return None
    parts = []
    if weather.get("summary"):
        parts.append(str(weather["summary"]))
    if weather.get("temperature") is not None:
        parts.append(f"기온 {weather['temperature']}도")
    if weather.get("precipitation_probability") is not None:
        parts.append(f"강수확률 {weather['precipitation_probability']}%")
    if (weather.get("precipitation") or 0) > 0:
        parts.append(f"현재 강수량 {weather['precipitation']}mm")
    return ", ".join(parts) or None


def fallback_message(
    alert: dict,
    weather: dict | None,
    travel_minutes: int | None,
    leave_at: datetime | None,
    leave_now: bool,
) -> str:
    """LLM을 쓸 수 없을 때 보내는 기본 문구"""

    lines = []
    if alert.get("kind") == "reminder":
        lines.append(f"요청하신 알림입니다: {alert.get('message') or ''}".strip())
    else:
        destination = alert.get("destination") or "목적지"
        if leave_now:
            lines.append(f"{destination}까지 지금 출발하세요.")
        elif leave_at:
            lines.append(f"{destination}까지 {format_hm(leave_at)}에 출발하세요.")
        else:
            arrival = parse_iso(alert.get("arrival_at"))
            when = f" {format_hm(arrival)}" if arrival else ""
            lines.append(f"{destination}{when} 약속 알림입니다.")
    if travel_minutes is not None:
        lines.append(f"예상 이동 시간은 약 {travel_minutes}분입니다.")
    if weather:
        weather_text = _weather_line(weather)
        if weather_text:
            lines.append(f"현재 날씨: {weather_text}.")
        rain_probability = weather.get("precipitation_probability") or 0
        current_precipitation = weather.get("precipitation") or 0
        if rain_probability >= 50 or current_precipitation > 0:
            lines.append("우산을 챙기세요.")
    if alert.get("items_hint"):
        lines.append(f"준비물: {alert['items_hint']}")
    return " ".join(lines)


def finalize_message(body: str, *, ai_generated: bool) -> str:
    """본문 길이를 제한하고 AI가 생성한 메시지에 작성 표시를 붙인다."""

    body = body.strip()
    suffix = f"\n{AI_LABEL}" if ai_generated else ""
    room = KAKAO_TEXT_LIMIT - len(suffix)
    if ai_generated:
        room = min(room, AI_BODY_LIMIT)
    if len(body) > room:
        body = body[: room - 1].rstrip() + "…"
    return body + suffix


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
    leave_at = ensure_aware(leave_at)
    leave_now = leave_at is not None and leave_at <= ensure_aware(now)
    departure_state = "알 수 없음"
    if leave_at is not None:
        departure_state = "지금 출발" if leave_now else "예정"
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
        f"출발 시점: {departure_state}",
        f"날씨: {_weather_line(weather) or '날씨 정보 없음'}",
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
        body = body.strip()
        while body.endswith(AI_LABEL):
            body = body.removesuffix(AI_LABEL).rstrip()
        if not body:
            raise LLMError("빈 응답")
        return finalize_message(body, ai_generated=True), True
    except LLMError:
        body = fallback_message(alert, weather, travel_minutes, leave_at, leave_now)
        return finalize_message(body, ai_generated=False), False
