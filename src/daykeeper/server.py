"""DayKeeper(데이키퍼) MCP 서버 — Streamable HTTP, Stateless.

PlayMCP 개발가이드 준수 사항:
- Streamable HTTP 전용, stateless (no session)
- 툴 7개, 모든 툴에 annotations 5종 지정
- description은 한글 우선 + 영문 병기 (가이드상 영문은 '권장'), 서비스명 영·국문 병기, 1024자 이내
- 서버명/툴명에 'kakao' 미포함
"""

from __future__ import annotations

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import service
from .dates import parse_date, today_kst

Relationship = Literal["partner", "friend", "parent", "coworker", "crush"]
Budget = Literal["under_10k", "10k_30k", "30k_50k", "over_50k"]
Tone = Literal["sweet", "funny", "polite", "casual"]
Category = Literal["official", "international", "love", "fun", "food", "animal", "culture"]

mcp = FastMCP(
    "DayKeeper",
    instructions=(
        "DayKeeper(데이키퍼) helps users celebrate special days: it looks up fun anniversaries "
        "and commemorative days (Korea-focused), recommends gifts by relationship and budget with "
        "ready-made gift-search links, drafts celebration messages in Korean, and calculates couple "
        "milestone anniversaries. All dates are handled in Korea Standard Time."
    ),
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8080")),
    stateless_http=True,
)

_READ_ONLY = dict(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def _parse_or_today(date_str: str | None):
    if not date_str:
        return today_kst()
    return parse_date(date_str)


@mcp.tool(
    annotations=ToolAnnotations(title="날짜별 기념일 조회", **_READ_ONLY),
    description=(
        "DayKeeper(데이키퍼)에서 특정 날짜의 기념일·데이·챙길 거리를 조회합니다. 각 기념일의 이름, "
        "카테고리, 유래, 챙김 포인트를 제공하고 장소가 어울리는 날은 지도 검색 링크도 담습니다. "
        "같은 날짜에 기념일이 여러 개인 경우가 많으니 사용자에게 먼저 모두 알려준 뒤 의도에 맞는 "
        "기념일을 중심으로 이어가세요. 등록된 기념일이 없는 날짜는 가까운 기념일을 대신 안내하며, "
        "date 생략 시 한국 표준시(KST) 오늘 기준입니다. "
        "(EN) Retrieves special days for a date from DayKeeper(데이키퍼): name, origin, care tips, "
        "and links. Multiple days may share one date - present them all first. Falls back to the "
        "nearest upcoming days; defaults to today KST."
    ),
)
def get_special_days(date: str | None = None) -> str:
    """date: YYYY-MM-DD (optional, default: today KST)"""
    try:
        target = _parse_or_today(date)
    except ValueError:
        return "날짜 형식이 올바르지 않아요. YYYY-MM-DD 형식으로 입력해 주세요. (예: 2026-08-08)"
    return service.render_special_days(target)


@mcp.tool(
    annotations=ToolAnnotations(title="다가오는 기념일", **_READ_ONLY),
    description=(
        "DayKeeper(데이키퍼)에서 앞으로 N일(1~30) 안의 기념일을 날짜·D-day·챙김 팁과 함께 "
        "시간순으로 보여줍니다. 연인·친구·가족·동료와 챙길 날을 미리 계획할 때 유용합니다. "
        "기본은 오늘(KST)부터이며 from_date(YYYY-MM-DD)를 주면 연말연시 같은 미래 구간도 조회할 "
        "수 있습니다. category로 결과를 좁힐 수 있습니다(official, international, love, fun, "
        "food, animal, culture). "
        "(EN) Lists upcoming special days within N days (1-30) from DayKeeper(데이키퍼) with D-day "
        "counts; from_date shifts the window to a future date; optional category filter."
    ),
)
def get_upcoming_special_days(
    days: int = 7,
    category: Category | None = None,
    from_date: str | None = None,
) -> str:
    days = max(1, min(30, days))
    try:
        start = _parse_or_today(from_date)
    except ValueError:
        return "from_date 형식이 올바르지 않아요. YYYY-MM-DD 형식으로 입력해 주세요. (예: 2026-12-20)"
    return service.render_upcoming(days, category, start=start)


@mcp.tool(
    annotations=ToolAnnotations(title="기념일 검색", **_READ_ONLY),
    description=(
        "DayKeeper(데이키퍼)에 등록된 기념일을 키워드로 검색합니다(예: 고양이, 커피, 초콜릿, 연인, "
        "설날). 일치하는 기념일의 날짜, D-day, 유래, 챙김 팁을 반환하며 category로 결과를 좁힐 수 "
        "있습니다. "
        "(EN) Searches special days in DayKeeper(데이키퍼) by keyword, returning dates, D-day "
        "counts, origins, and celebration tips; optional category filter."
    ),
)
def search_special_days(query: str, category: Category | None = None) -> str:
    if not query.strip():
        return "검색어를 입력해 주세요. (예: 고양이, 커피, 초콜릿)"
    return service.render_search(query, category)


@mcp.tool(
    annotations=ToolAnnotations(title="선물 추천", **_READ_ONLY),
    description=(
        "DayKeeper(데이키퍼)가 상황(밸런타인데이 같은 기념일 이름, 또는 생일/100일/집들이 같은 "
        "상황)과 관계(partner/friend/parent/coworker/crush), 예산에 맞춰 선물을 추천합니다. "
        "추천마다 어울리는 이유, 가격대, 바로 쓸 수 있는 선물 검색 링크가 포함되며, 링크는 반드시 "
        "사용자에게 함께 전달하세요. "
        "(EN) Recommends gifts from DayKeeper(데이키퍼) for an occasion, tailored to relationship "
        "and budget; each item includes a reason, price range, and a ready-made gift-search link."
    ),
)
def recommend_gifts(occasion: str, relationship: Relationship, budget: Budget | None = None) -> str:
    return service.render_gifts(occasion, relationship, budget)


@mcp.tool(
    annotations=ToolAnnotations(title="축하 메시지 생성", **_READ_ONLY),
    description=(
        "DayKeeper(데이키퍼)가 상황·관계(partner/friend/parent/coworker/crush)·톤"
        "(sweet/funny/polite/casual)에 맞춘, 바로 보낼 수 있는 한국어 축하 메시지 초안 3개를 "
        "생성합니다. recipient_name을 주면 받는 사람 이름을 앞에 붙입니다. 기념일을 찾았거나 "
        "선물을 고른 직후에 쓰기 좋습니다. "
        "(EN) Generates three ready-to-send Korean celebration drafts from DayKeeper(데이키퍼), "
        "tailored to occasion, relationship, and tone; optionally prefixes the recipient's name."
    ),
)
def generate_celebration_message(
    occasion: str,
    relationship: Relationship,
    tone: Tone = "casual",
    recipient_name: str | None = None,
) -> str:
    return service.render_messages(occasion, relationship, tone, recipient_name)


@mcp.tool(
    annotations=ToolAnnotations(title="연인 마일스톤 계산", **_READ_ONLY),
    description=(
        "DayKeeper(데이키퍼)가 사귀기 시작한 날짜(YYYY-MM-DD)를 기준으로 커플 마일스톤을 "
        "계산합니다. 오늘까지 함께한 일수(한국 관례대로 시작일이 1일째), 다가오는 100일 단위·주년 "
        "기념일의 날짜와 D-day를 알려주며, 마일스톤이 알려진 기념일과 겹치면 그 이름을 함께 "
        "표시하니 소개할 때 같이 언급하세요. 순수 계산만 하며 아무것도 저장하지 않습니다. "
        "(EN) Calculates couple milestones from DayKeeper(데이키퍼) based on the start date (day 1, "
        "Korean convention): upcoming 100-day and yearly anniversaries with D-day counts, annotated "
        "with coinciding special days. Nothing is stored."
    ),
)
def calc_couple_milestones(start_date: str, count: int = 5) -> str:
    try:
        start = parse_date(start_date)
    except ValueError:
        return "날짜 형식이 올바르지 않아요. YYYY-MM-DD 형식으로 입력해 주세요. (예: 2025-05-02)"
    count = max(1, min(12, count))
    return service.render_milestones(start, count)


@mcp.tool(
    annotations=ToolAnnotations(title="원스톱 챙김 플랜", **_READ_ONLY),
    description=(
        "DayKeeper(데이키퍼)가 지정한 날짜(기본: 오늘 KST)의 원스톱 챙김 플랜을 만듭니다: 무슨 "
        "날인지, 관계·예산에 맞춘 선물 아이디어(선물 검색 링크 포함), 보낼 메시지 초안까지 한 "
        "번에 제공합니다. 해당 날짜에 기념일이 없으면 가장 가까운 기념일 기준으로 만듭니다. "
        "(EN) Creates a one-stop celebration plan from DayKeeper(데이키퍼) for a date: the special "
        "day, gift ideas with search links, and message drafts; uses the nearest upcoming day if "
        "none falls on the date."
    ),
)
def create_celebration_plan(
    relationship: Relationship,
    date: str | None = None,
    budget: Budget | None = None,
) -> str:
    try:
        target = _parse_or_today(date)
    except ValueError:
        return "날짜 형식이 올바르지 않아요. YYYY-MM-DD 형식으로 입력해 주세요."
    return service.render_plan(target, relationship, budget)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "daykeeper"})


@mcp.custom_route("/", methods=["GET"])
async def root(_: Request) -> JSONResponse:
    return JSONResponse({"service": "DayKeeper", "mcp_endpoint": "/mcp", "health": "/health"})


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
