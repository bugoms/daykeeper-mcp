"""KST 날짜 계산 유틸리티. 서버가 UTC에서 돌아도 '오늘'은 항상 Asia/Seoul 기준."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today_kst() -> date:
    return datetime.now(KST).date()


def parse_date(value: str) -> date:
    """YYYY-MM-DD 문자열을 date로 변환. 형식이 틀리면 ValueError."""
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def dday_label(target: date, today: date) -> str:
    diff = (target - today).days
    if diff == 0:
        return "오늘"
    if diff > 0:
        return f"D-{diff}"
    return f"D+{-diff}"


def next_occurrence(month: int, day: int, today: date) -> date:
    """month/day의 다음 도래일 (오늘 포함). 2/29는 평년이면 2/28로 처리."""
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            candidate = date(year, 2, 28)
        if candidate >= today:
            return candidate
    raise AssertionError("unreachable")


def add_years(start: date, years: int) -> date:
    """윤년 2/29 시작일은 평년에서 2/28로 처리."""
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        return start.replace(year=start.year + years, day=28)


def couple_milestones(start: date, today: date, count: int) -> tuple[int, list[tuple[str, date]]]:
    """사귄 날(=1일째) 기준 현재 일수와 다가오는 마일스톤 목록을 반환.

    마일스톤: 100일 단위(사귄 날이 1일째이므로 N일째 = start + (N-1)일) + n주년.
    오늘이 마일스톤이면 목록에 포함된다(D-0).
    """
    days_together = (today - start).days + 1
    milestones: list[tuple[str, date]] = []

    n = 100
    while len(milestones) < count + 20 and n <= days_together + 36500:
        d = start + timedelta(days=n - 1)
        if d >= today:
            milestones.append((f"{n}일", d))
        n += 100

    year = 1
    while year <= 100:
        d = add_years(start, year)
        if d >= today:
            milestones.append((f"{year}주년", d))
        if len([m for m in milestones if m[0].endswith("주년")]) >= count:
            break
        year += 1

    milestones.sort(key=lambda m: (m[1], m[0]))
    return days_together, milestones[:count]
