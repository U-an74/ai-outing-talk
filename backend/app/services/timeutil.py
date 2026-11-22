# 시간대(KST) 처리 도우미

from datetime import datetime, timedelta, timezone


KST = timezone(timedelta(hours=9), name="Asia/Seoul")

WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


def now_kst() -> datetime:
    """현재 한국 시각"""
    return datetime.now(KST)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime | None) -> datetime | None:
    """시간대 정보가 없는 시각은 한국 시각으로 간주"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value


def parse_iso(value) -> datetime | None:
    """ISO 8601 문자열을 시간대가 있는 datetime으로 변환"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return ensure_aware(value)
    try:
        text = str(value).strip().replace("Z", "+00:00")
        return ensure_aware(datetime.fromisoformat(text))
    except ValueError:
        return None


def to_iso_kst(value: datetime | None) -> str | None:
    """datetime을 한국 시각 ISO 문자열로 변환"""
    if value is None:
        return None
    return ensure_aware(value).astimezone(KST).isoformat()


def describe_now(value: datetime) -> str:
    """LLM에 전달할 현재 시각 설명 (예: 2026-11-22T14:30:00+09:00 (일요일))"""
    local = ensure_aware(value).astimezone(KST)
    return f"{local.isoformat(timespec='minutes')} ({WEEKDAYS_KO[local.weekday()]}요일)"


def format_hm(value: datetime | None) -> str | None:
    """사람이 읽는 시각 (예: 오후 1:20)"""
    if value is None:
        return None
    local = ensure_aware(value).astimezone(KST)
    period = "오전" if local.hour < 12 else "오후"
    hour = local.hour % 12 or 12
    return f"{period} {hour}:{local.minute:02d}"


def next_occurrence(current: datetime, repeat: str, after: datetime) -> datetime | None:
    """
    반복 알림의 다음 발송 시각
    - daily: 매일 같은 시각
    - weekdays: 월~금 같은 시각
    after 이후의 가장 가까운 시각을 반환하고, 반복이 없으면 None
    """

    if repeat not in ("daily", "weekdays"):
        return None

    local = ensure_aware(current).astimezone(KST)
    after = ensure_aware(after)

    candidate = local + timedelta(days=1)
    for _ in range(14):
        if candidate > after and (repeat == "daily" or candidate.weekday() < 5):
            return candidate
        candidate += timedelta(days=1)
    return None


def first_occurrence(start: datetime, repeat: str, after: datetime) -> datetime:
    """반복 알림 등록 시 첫 발송 시각 (이미 지났거나 주말이면 다음 해당 날짜로)"""

    start = ensure_aware(start)
    if start > after and (repeat != "weekdays" or start.astimezone(KST).weekday() < 5):
        return start
    return next_occurrence(start, repeat, after) or start
