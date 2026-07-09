"""조회·추천·생성 핵심 로직. 전부 내장 JSON 기반 순수 함수 — 외부 호출 없음."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

from .dates import couple_milestones, dday_label, next_occurrence, today_kst

_DATA_DIR = Path(__file__).parent / "data"

SPECIAL_DAYS: list[dict] = json.loads((_DATA_DIR / "special_days.json").read_text(encoding="utf-8"))
_GIFTS: dict = json.loads((_DATA_DIR / "gifts.json").read_text(encoding="utf-8"))
GIFT_ITEMS: list[dict] = _GIFTS["items"]
OCCASION_TAGS: dict[str, list[str]] = _GIFTS["occasions"]
MESSAGES: dict = json.loads((_DATA_DIR / "messages.json").read_text(encoding="utf-8"))

CATEGORIES = sorted({d["category"] for d in SPECIAL_DAYS})

RELATIONSHIP_KO = {
    "partner": "연인",
    "friend": "친구",
    "parent": "부모님",
    "coworker": "동료",
    "crush": "썸",
}
BUDGET_KO = {
    "under_10k": "1만원 이하",
    "10k_30k": "1~3만원",
    "30k_50k": "3~5만원",
    "over_50k": "5만원 이상",
}
_BUDGET_ORDER = ["under_10k", "10k_30k", "30k_50k", "over_50k"]


def gift_link(keyword: str) -> str:
    return f"https://gift.kakao.com/search/result?query={quote(keyword)}"


def map_link(query: str) -> str:
    return f"https://map.kakao.com/?q={quote(query)}"


# ---------------------------------------------------------------- 기념일 조회

def days_for(month: int, day: int) -> list[dict]:
    return [d for d in SPECIAL_DAYS if d["month"] == month and d["day"] == day]


def _entry_lines(entry: dict, target: date | None = None, today: date | None = None) -> list[str]:
    head = f"**{entry['name']}** ({entry['name_en']})"
    if target is not None and today is not None:
        head += f" — {target.month}/{target.day} ({dday_label(target, today)})"
    lines = [f"- {head}", f"  - {entry['origin']}", f"  - 💡 {entry['care_point']}"]
    if entry.get("place_query"):
        lines.append(f"  - 📍 [카카오맵에서 '{entry['place_query']}' 검색]({map_link(entry['place_query'])})")
    return lines


def render_special_days(target: date, today: date | None = None) -> str:
    today = today or today_kst()
    entries = days_for(target.month, target.day)
    title = f"## {target.year}년 {target.month}월 {target.day}일"
    if target == today:
        title += " (오늘)"

    if entries:
        lines = [title, ""]
        for e in entries:
            lines.extend(_entry_lines(e))
        lines.append("")
        lines.append("👉 선물이 필요하면 `recommend_gifts`, 보낼 메시지는 `generate_celebration_message`를 사용하세요.")
        return "\n".join(lines)

    upcoming = _upcoming_entries(target, 30, None)[:3]
    lines = [title, "", "이 날짜에 등록된 기념일은 없어요. 대신 가까운 챙길 만한 날을 알려드릴게요:", ""]
    for target_date, e in upcoming:
        lines.extend(_entry_lines(e, target_date, today))
    return "\n".join(lines)


def _upcoming_entries(start: date, days: int, category: str | None) -> list[tuple[date, dict]]:
    result = []
    for e in SPECIAL_DAYS:
        if category and e["category"] != category:
            continue
        occ = next_occurrence(e["month"], e["day"], start)
        if (occ - start).days <= days:
            result.append((occ, e))
    result.sort(key=lambda t: (t[0], t[1]["id"]))
    return result


def render_upcoming(days: int, category: str | None = None, today: date | None = None) -> str:
    today = today or today_kst()
    entries = _upcoming_entries(today, days, category)
    scope = f"오늘부터 {days}일 안"
    if category:
        scope += f" ({category} 카테고리)"
    if not entries:
        return f"## 다가오는 기념일\n\n{scope}에는 등록된 기념일이 없어요. `days`를 늘려서 다시 조회해 보세요."
    lines = [f"## 다가오는 기념일 ({scope})", ""]
    for target, e in entries:
        lines.append(f"- **{target.month}/{target.day} ({dday_label(target, today)})** {e['name']} — {e['care_point']}")
    return "\n".join(lines)


def render_search(query: str, category: str | None = None, today: date | None = None) -> str:
    today = today or today_kst()
    q = query.strip().lower()
    matches = []
    for e in SPECIAL_DAYS:
        if category and e["category"] != category:
            continue
        haystack = " ".join([e["name"], e["name_en"], e["origin"], e["care_point"], " ".join(e["gift_tags"])]).lower()
        if q in haystack:
            matches.append(e)
    if not matches:
        return f"'{query}'와 관련된 기념일을 찾지 못했어요. 다른 키워드(예: 고양이, 커피, 초콜릿, 연인)로 검색해 보세요."
    lines = [f"## '{query}' 관련 기념일 ({len(matches)}건)", ""]
    for e in matches:
        occ = next_occurrence(e["month"], e["day"], today)
        lines.extend(_entry_lines(e, occ, today))
    return "\n".join(lines)


# ---------------------------------------------------------------- 선물 추천

def _occasion_tags(occasion: str) -> list[str]:
    occ = occasion.strip().lower()
    for e in SPECIAL_DAYS:
        if e["name"].lower() in occ or occ in e["name"].lower():
            if e["gift_tags"]:
                return e["gift_tags"]
    for key, tags in OCCASION_TAGS.items():
        if key in occasion:
            return tags
    return []


def _pick_gifts(tags: list[str], relationship: str, budget: str | None, limit: int = 4) -> list[dict]:
    def score(item: dict) -> tuple:
        tag_overlap = len(set(item["tags"]) & set(tags))
        budget_match = 1 if (budget and item["budget"] == budget) else 0
        return (-tag_overlap, -budget_match, item["id"])

    candidates = [i for i in GIFT_ITEMS if relationship in i["relationships"]]
    if budget:
        exact = [i for i in candidates if i["budget"] == budget]
        picked = sorted([i for i in exact if set(i["tags"]) & set(tags)], key=score)
        if len(picked) < limit:
            picked += [i for i in sorted(exact, key=score) if i not in picked]
        if len(picked) < 3:  # 예산 내 후보가 부족하면 인접 예산까지 완화
            others = sorted([i for i in candidates if i not in picked], key=score)
            picked += others
        return picked[:limit]
    picked = sorted([i for i in candidates if set(i["tags"]) & set(tags)], key=score)
    if len(picked) < limit:
        picked += [i for i in sorted(candidates, key=score) if i not in picked]
    return picked[:limit]


def render_gifts(occasion: str, relationship: str, budget: str | None = None) -> str:
    tags = _occasion_tags(occasion)
    items = _pick_gifts(tags, relationship, budget)
    rel_ko = RELATIONSHIP_KO.get(relationship, relationship)
    scope = f"{rel_ko}에게" + (f", 예산 {BUDGET_KO[budget]}" if budget else "")
    lines = [f"## '{occasion}' 선물 추천 ({scope})", ""]
    for item in items:
        kw = item["keywords"][0]
        lines.append(f"- **{item['name']}** ({item['price_range']})")
        lines.append(f"  - {item['reason']}")
        lines.append(f"  - 🎁 [선물하기에서 '{kw}' 검색]({gift_link(kw)})")
    day = next((e for e in SPECIAL_DAYS if e["name"] in occasion and e.get("place_query")), None)
    if day:
        lines.append("")
        lines.append(f"📍 함께 가기 좋은 곳: [카카오맵에서 '{day['place_query']}' 검색]({map_link(day['place_query'])})")
    lines.append("")
    lines.append("✉️ 함께 보낼 메시지는 `generate_celebration_message`로 만들 수 있어요.")
    return "\n".join(lines)


# ---------------------------------------------------------------- 메시지 생성

def _has_batchim(word: str) -> bool:
    """마지막 유효 글자의 받침 유무. 한글 음절과 숫자만 판정, 그 외는 받침 없음 취급."""
    for ch in reversed(word.strip()):
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
        if ch.isdigit():
            return ch in "013678"  # 영·일·삼·육·칠·팔은 받침 있음
    return False


def _fill_occasion(template: str, occasion: str) -> str:
    """{occasion} 치환 + 뒤따르는 조사(이/을) 받침 처리.

    예: '실버데이' + '{occasion}이래' → '실버데이래', '핼러윈' → '핼러윈이래'
    """
    parts = template.split("{occasion}")
    if len(parts) == 1:
        return template
    has_b = _has_batchim(occasion)
    result = parts[0]
    for seg in parts[1:]:
        if not has_b and seg.startswith("이"):
            seg = seg[1:]
        elif not has_b and seg.startswith("을"):
            seg = "를" + seg[1:]
        result += occasion + seg
    return result


def render_messages(occasion: str, relationship: str, tone: str = "casual", recipient_name: str | None = None) -> str:
    templates = MESSAGES.get(relationship, {}).get(tone)
    if not templates:
        return f"지원하지 않는 조합이에요. relationship은 {list(MESSAGES)}, tone은 sweet/funny/polite/casual 중에서 골라 주세요."
    rel_ko = RELATIONSHIP_KO.get(relationship, relationship)
    lines = [f"## '{occasion}' 메시지 초안 ({rel_ko} · {tone})", ""]
    for i, tpl in enumerate(templates, 1):
        msg = _fill_occasion(tpl, occasion)
        if recipient_name:
            prefix = f"{recipient_name}님, " if tone == "polite" else f"{recipient_name}~ "
            msg = prefix + msg
        lines.append(f"{i}. {msg}")
    lines.append("")
    lines.append("마음에 드는 초안을 골라 자유롭게 다듬어 보내세요.")
    return "\n".join(lines)


# ---------------------------------------------------------------- 마일스톤

def render_milestones(start: date, count: int = 5, today: date | None = None) -> str:
    today = today or today_kst()
    if start > today:
        return "시작일이 미래 날짜예요. 사귀기 시작한 날짜를 YYYY-MM-DD 형식으로 알려 주세요."
    days_together, milestones = couple_milestones(start, today, count)
    lines = [f"## 우리 사이 마일스톤 (시작일 {start.isoformat()})", "", f"오늘로 **{days_together}일째**예요! 💕", ""]
    for label, d in milestones:
        marker = " 🎉 **오늘!**" if d == today else ""
        lines.append(f"- **{label}**: {d.isoformat()} ({dday_label(d, today)}){marker}")
    lines.append("")
    lines.append("🎁 기념일 선물이 필요하면 `recommend_gifts`에 '100일'이나 '1주년'을 넣어 보세요.")
    return "\n".join(lines)


# ---------------------------------------------------------------- 원스톱 플랜

def render_plan(target: date, relationship: str, budget: str | None = None, today: date | None = None) -> str:
    today = today or today_kst()
    entries = days_for(target.month, target.day)
    rel_ko = RELATIONSHIP_KO.get(relationship, relationship)

    if not entries:
        upcoming = _upcoming_entries(target, 30, None)
        if not upcoming:
            return "가까운 기념일을 찾지 못했어요."
        target, main = upcoming[0]
        note = f"요청한 날짜에 기념일이 없어 가장 가까운 **{main['name']}** ({target.month}/{target.day}, {dday_label(target, today)}) 기준으로 플랜을 만들었어요.\n"
    else:
        main = next((e for e in entries if e["gift_tags"]), entries[0])
        note = ""

    lines = [f"# {main['name']} 챙김 플랜 ({rel_ko})", ""]
    if note:
        lines.append(note)
    lines.append(f"**1. 오늘 무슨 날?** — {main['origin']}")
    others = [e["name"] for e in entries if e["id"] != main["id"]]
    if others:
        lines.append(f"   (같은 날: {', '.join(others)})")
    lines.append(f"   💡 {main['care_point']}")
    if main.get("place_query"):
        lines.append(f"   📍 [카카오맵에서 '{main['place_query']}' 검색]({map_link(main['place_query'])})")
    lines.append("")

    lines.append("**2. 선물 아이디어**")
    for item in _pick_gifts(main["gift_tags"], relationship, budget, limit=3):
        kw = item["keywords"][0]
        lines.append(f"   - {item['name']} ({item['price_range']}) — {item['reason']} · [🎁 선물 검색]({gift_link(kw)})")
    lines.append("")

    lines.append("**3. 보낼 메시지 초안**")
    tone = "sweet" if relationship in ("partner", "crush") else "casual"
    for i, tpl in enumerate(MESSAGES[relationship][tone][:2], 1):
        lines.append(f"   {i}. {_fill_occasion(tpl, main['name'])}")
    lines.append("")
    lines.append("이대로 보내도 좋고, 예산·톤을 바꿔 다시 요청해도 돼요.")
    return "\n".join(lines)
