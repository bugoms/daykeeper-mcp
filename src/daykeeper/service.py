"""조회·추천·생성 핵심 로직. 전부 내장 JSON 기반 순수 함수 — 런타임 외부 호출 없음.

데이터 소스 2종:
- special_days.json  : 큐레이션 기념일 (월/일 고정, 재미있는 날 중심)
- public_days.json   : KASI 특일 정보 API 빌드 타임 스냅샷 (연도별 공휴일·명절·절기·법정기념일)
  → scripts/sync_public_days.py 로 갱신. 서버는 파일만 읽으므로 API 키 불필요.
"""

from __future__ import annotations

import json
from datetime import date
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

# ------------------------------------------------- 공공데이터(KASI 특일) 로드

KIND_KO = {
    "holiday": "공휴일",
    "national": "국경일",
    "anniversary": "기념일",
    "solar_term": "24절기",
    "sundry": "세시풍속",
}
_KIND_ORDER = {"holiday": 0, "national": 1, "sundry": 2, "solar_term": 3, "anniversary": 4}
_KIND_CARE = {
    "holiday": "공휴일이에요. 소중한 사람과 함께 보내기 좋은 날",
    "national": "국경일의 의미를 되새겨 보세요",
    "anniversary": "국가 지정 기념일이에요. 관련된 지인이 있다면 안부를 전해 보세요",
    "solar_term": "계절의 변화를 알리는 24절기예요",
    "sundry": "전통 세시풍속이에요",
}
# 큐레이션 데이터와 이름이 다른 동일 기념일 (공공데이터 쪽을 숨김)
DEDUP_ALIASES = {
    "기독탄신일": "크리스마스",
    "1월1일": "새해 첫날",
    "노동절": "근로자의 날",
}


def _norm_public(e: dict) -> dict:
    kind = e["kind"]
    name = e["name"]
    is_substitute = name.startswith("대체공휴일")
    if is_substitute:
        badge = "대체공휴일"
        default_care = "원래 공휴일이 휴일과 겹쳐 별도로 지정된 대체공휴일이에요. 연휴 계획 세우기 좋은 날"
    else:
        badge = KIND_KO[kind]
        default_care = _KIND_CARE[kind]
    return {
        "id": f"pub-{e['year']:04d}{e['month']:02d}{e['day']:02d}-{name}",
        "name": name,
        "name_en": None,
        "badge": badge,
        "category": "official" if kind in ("holiday", "national", "anniversary") else "culture",
        "origin": None,
        "care_point": e.get("care_point") or default_care,
        "gift_tags": e.get("gift_tags") or [],
        "place_query": e.get("place_query"),
        "year": e["year"],
        "month": e["month"],
        "day": e["day"],
        "kind": kind,
        "is_holiday": e.get("is_holiday", False),
        "public": True,
    }


_PUBLIC_PATH = _DATA_DIR / "public_days.json"
if _PUBLIC_PATH.exists():
    _raw_public = json.loads(_PUBLIC_PATH.read_text(encoding="utf-8"))
    PUBLIC_ENTRIES: list[dict] = [_norm_public(e) for e in _raw_public.get("days", [])]
    PUBLIC_YEARS: list[int] = _raw_public.get("years", [])
else:  # 동기화 전에도 서버·테스트가 동작하도록
    PUBLIC_ENTRIES = []
    PUBLIC_YEARS = []


def gift_link(keyword: str) -> str:
    return f"https://gift.kakao.com/search/result?query={quote(keyword)}"


def map_link(query: str) -> str:
    return f"https://map.kakao.com/?q={quote(query)}"


# ---------------------------------------------------------------- 기념일 조회

def days_for(month: int, day: int) -> list[dict]:
    return [d for d in SPECIAL_DAYS if d["month"] == month and d["day"] == day]


def entries_for_date(target: date) -> tuple[list[dict], list[dict]]:
    """해당 날짜의 (큐레이션, 공공데이터) 항목. 이름 중복은 큐레이션 우선."""
    curated = days_for(target.month, target.day)
    curated_names = {c["name"] for c in curated}
    public = []
    for p in PUBLIC_ENTRIES:
        if (p["year"], p["month"], p["day"]) != (target.year, target.month, target.day):
            continue
        canon = DEDUP_ALIASES.get(p["name"], p["name"])
        if canon in curated_names:
            continue
        public.append(p)
    public.sort(key=lambda p: (_KIND_ORDER.get(p["kind"], 9), p["name"]))
    return curated, public


def _tag_keyword(tags: list[str]) -> str | None:
    """선물 태그에 가장 잘 맞는 대표 검색 키워드 (결정적: 파일 순서 우선)."""
    best, best_overlap = None, 0
    for item in GIFT_ITEMS:
        overlap = len(set(item["tags"]) & set(tags))
        if overlap > best_overlap:
            best, best_overlap = item, overlap
    return best["keywords"][0] if best else None


def _entry_lines(entry: dict, target: date | None = None, today: date | None = None) -> list[str]:
    head = f"**{entry['name']}**"
    if entry.get("name_en"):
        head += f" ({entry['name_en']})"
    if entry.get("badge"):
        head += f" `{entry['badge']}`"
    if target is not None and today is not None:
        head += f" — {target.month}/{target.day} ({dday_label(target, today)})"
    lines = [f"- {head}"]
    if entry.get("origin"):
        lines.append(f"  - {entry['origin']}")
    lines.append(f"  - 💡 {entry['care_point']}")
    if entry.get("gift_tags"):
        kw = _tag_keyword(entry["gift_tags"])
        if kw:
            lines.append(f"  - 🎁 [선물하기에서 '{kw}' 검색]({gift_link(kw)})")
    if entry.get("place_query"):
        lines.append(f"  - 📍 [카카오맵에서 '{entry['place_query']}' 검색]({map_link(entry['place_query'])})")
    return lines


# ---------------------------------------------------------------- 공휴일 안내

def _canon(name: str) -> str:
    return DEDUP_ALIASES.get(name, name)


def nearest_holidays(ref: date) -> tuple[tuple[date, dict] | None, tuple[date, dict] | None]:
    """ref 기준 (가장 최근 지나간 공휴일, 다음 공휴일). 대체공휴일 포함, is_holiday 기준."""
    prev_h = next_h = None
    holidays = sorted(
        ((date(p["year"], p["month"], p["day"]), p) for p in PUBLIC_ENTRIES if p.get("is_holiday")),
        key=lambda t: t[0],
    )
    for d, p in holidays:
        if d < ref:
            prev_h = (d, p)
        elif d > ref:
            next_h = (d, p)
            break
    return prev_h, next_h


def _holiday_footer(ref: date, today: date, include_prev: bool = True) -> list[str]:
    prev_h, next_h = nearest_holidays(ref)
    parts = []
    if next_h:
        d, p = next_h
        parts.append(f"다음 공휴일 **{_canon(p['name'])}** {d.month}/{d.day} ({dday_label(d, today)})")
    if include_prev and prev_h:
        d, p = prev_h
        parts.append(f"최근 지난 공휴일 **{_canon(p['name'])}** {d.month}/{d.day} ({dday_label(d, today)})")
    if not parts:
        return []
    return ["", "🗓️ " + " · ".join(parts)]


def render_special_days(target: date, today: date | None = None) -> str:
    today = today or today_kst()
    curated, public = entries_for_date(target)
    title = f"## {target.year}년 {target.month}월 {target.day}일"
    if target == today:
        title += " (오늘)"

    if curated or public:
        lines = [title, ""]
        for e in curated:
            lines.extend(_entry_lines(e))
        shown = public[:5]
        for e in shown:
            lines.extend(_entry_lines(e))
        if len(public) > len(shown):
            lines.append(f"- 이 외 {len(public) - len(shown)}건의 기념일이 더 있어요.")
        lines.extend(_holiday_footer(target, today))
        lines.append("")
        lines.append("👉 선물이 필요하면 `recommend_gifts`, 보낼 메시지는 `generate_celebration_message`를 사용하세요.")
        return "\n".join(lines)

    upcoming = _upcoming_entries(target, 30, None)[:3]
    lines = [title, "", "이 날짜에 등록된 기념일은 없어요. 대신 가까운 챙길 만한 날을 알려드릴게요:", ""]
    for target_date, e in upcoming:
        lines.extend(_entry_lines(e, target_date, today))
    lines.extend(_holiday_footer(target, today))
    return "\n".join(lines)


def _upcoming_entries(start: date, days: int, category: str | None) -> list[tuple[date, dict]]:
    result: list[tuple[date, dict]] = []
    seen: set[tuple[date, str]] = set()
    for e in SPECIAL_DAYS:
        if category and e["category"] != category:
            continue
        occ = next_occurrence(e["month"], e["day"], start)
        if (occ - start).days <= days:
            result.append((occ, e))
            seen.add((occ, e["name"]))
    for p in PUBLIC_ENTRIES:
        try:
            d = date(p["year"], p["month"], p["day"])
        except ValueError:
            continue
        if not 0 <= (d - start).days <= days:
            continue
        if category and p["category"] != category:
            continue
        canon = DEDUP_ALIASES.get(p["name"], p["name"])
        if (d, canon) in seen:
            continue
        result.append((d, p))
    result.sort(key=lambda t: (t[0], t[1].get("public", False), _KIND_ORDER.get(t[1].get("kind"), -1), t[1]["id"]))
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
    has_holiday = False
    for target, e in entries:
        badge = f" `{e['badge']}`" if e.get("badge") else ""
        if e.get("is_holiday"):
            has_holiday = True
        lines.append(f"- **{target.month}/{target.day} ({dday_label(target, today)})** {e['name']}{badge} — {e['care_point']}")
    if not has_holiday:  # 조회 기간에 공휴일이 없으면 다음 공휴일을 따로 안내
        lines.extend(_holiday_footer(today, today, include_prev=False))
    return "\n".join(lines)


def render_search(query: str, category: str | None = None, today: date | None = None) -> str:
    today = today or today_kst()
    q = query.strip().lower()

    curated_matches = []
    for e in SPECIAL_DAYS:
        if category and e["category"] != category:
            continue
        haystack = " ".join([e["name"], e["name_en"], e["origin"], e["care_point"], " ".join(e["gift_tags"])]).lower()
        if q in haystack:
            curated_matches.append(e)
    curated_names = {e["name"] for e in curated_matches}

    wants_holiday = "휴일" in q  # "공휴일", "휴일" 검색 → 공휴일 전체 매칭
    public_matches: list[tuple[date, dict]] = []
    for p in PUBLIC_ENTRIES:
        if category and p["category"] != category:
            continue
        if q not in p["name"].lower() and not (wants_holiday and p.get("is_holiday")):
            continue
        canon = DEDUP_ALIASES.get(p["name"], p["name"])
        if canon in curated_names:
            continue
        d = date(p["year"], p["month"], p["day"])
        if d >= today:
            public_matches.append((d, p))
    public_matches.sort(key=lambda t: t[0])
    public_matches = public_matches[:5]

    total = len(curated_matches) + len(public_matches)
    if total == 0:
        return f"'{query}'와 관련된 기념일을 찾지 못했어요. 다른 키워드(예: 고양이, 커피, 설날, 연인)로 검색해 보세요."
    lines = [f"## '{query}' 관련 기념일 ({total}건)", ""]
    for e in curated_matches:
        occ = next_occurrence(e["month"], e["day"], today)
        lines.extend(_entry_lines(e, occ, today))
    for d, p in public_matches:
        lines.extend(_entry_lines(p, d, today))
    return "\n".join(lines)


# ---------------------------------------------------------------- 선물 추천

def _occasion_tags(occasion: str) -> list[str]:
    occ = occasion.strip().lower()
    for e in SPECIAL_DAYS:
        if e["name"].lower() in occ or occ in e["name"].lower():
            if e["gift_tags"]:
                return e["gift_tags"]
    for p in PUBLIC_ENTRIES:  # 설날·추석·복날 등 enrichment된 공공 기념일
        if p["gift_tags"] and (p["name"] in occasion or occ in p["name"].lower()):
            return p["gift_tags"]
    for key, tags in OCCASION_TAGS.items():
        if key in occasion:
            return tags
    return []


def _occasion_place(occasion: str) -> str | None:
    day = next((e for e in SPECIAL_DAYS if e["name"] in occasion and e.get("place_query")), None)
    if day:
        return day["place_query"]
    pub = next((p for p in PUBLIC_ENTRIES if p["name"] in occasion and p.get("place_query")), None)
    return pub["place_query"] if pub else None


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
    place = _occasion_place(occasion)
    if place:
        lines.append("")
        lines.append(f"📍 함께 가기 좋은 곳: [카카오맵에서 '{place}' 검색]({map_link(place)})")
    lines.append("")
    lines.append("✉️ 함께 보낼 메시지는 `generate_celebration_message`로 만들 수 있어요.")
    lines.append("")
    lines.append("※ 사용자에게 선물을 추천할 때는 위 각 선물의 선물하기 검색 링크를 반드시 함께 전달하세요.")
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
    curated, public = entries_for_date(target)
    merged = curated + public
    rel_ko = RELATIONSHIP_KO.get(relationship, relationship)

    if not merged:
        upcoming = _upcoming_entries(target, 30, None)
        if not upcoming:
            return "가까운 기념일을 찾지 못했어요."
        target, main = upcoming[0]
        note = f"요청한 날짜에 기념일이 없어 가장 가까운 **{main['name']}** ({target.month}/{target.day}, {dday_label(target, today)}) 기준으로 플랜을 만들었어요.\n"
    else:
        main = next((e for e in merged if e["gift_tags"]), merged[0])
        note = ""

    lines = [f"# {main['name']} 챙김 플랜 ({rel_ko})", ""]
    if note:
        lines.append(note)
    badge = main.get("badge", "기념일")
    about = main.get("origin") or f"{badge}{'으로' if _has_batchim(badge) else '로'} 지정된 날이에요"
    lines.append(f"**1. 오늘 무슨 날?** — {about}")
    others = [e["name"] for e in merged if e["id"] != main.get("id")]
    if others:
        lines.append(f"   (같은 날: {', '.join(others[:4])})")
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
    lines.append("")
    lines.append("※ 사용자에게 선물을 추천할 때는 위 각 선물의 선물하기 검색 링크를 반드시 함께 전달하세요.")
    return "\n".join(lines)
