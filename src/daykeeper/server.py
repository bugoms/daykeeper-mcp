"""DayKeeper(데이키퍼) MCP 서버 — Streamable HTTP, Stateless.

PlayMCP 개발가이드 준수 사항:
- Streamable HTTP 전용, stateless (no session)
- 툴 7개, 모든 툴에 annotations 5종 지정
- description은 영문 + 서비스명 병기, 1024자 이내
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
        "Retrieves special days, fun anniversaries, and commemorative days for a specific date "
        "from DayKeeper(데이키퍼). Returns each day's name, category, origin, and a care tip for "
        "celebrating it, plus a map-search link when the day has a place context. If the date has "
        "no registered special day, the nearest upcoming special days are suggested instead. "
        "The date defaults to today in Korea Standard Time when omitted."
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
        "Lists upcoming special days and anniversaries within the next N days (1-30) from "
        "DayKeeper(데이키퍼), each with its date, D-day count, and a celebration tip. Useful for "
        "planning ahead which days to celebrate with a partner, friend, family member, or coworker. "
        "An optional category filter narrows results (official, international, love, fun, food, "
        "animal, culture)."
    ),
)
def get_upcoming_special_days(days: int = 7, category: Category | None = None) -> str:
    days = max(1, min(30, days))
    return service.render_upcoming(days, category)


@mcp.tool(
    annotations=ToolAnnotations(title="기념일 검색", **_READ_ONLY),
    description=(
        "Searches special days registered in DayKeeper(데이키퍼) by keyword, e.g. cat(고양이), "
        "coffee(커피), chocolate(초콜릿), couple(연인). Returns matching days with their dates, "
        "D-day counts, origins, and celebration tips. An optional category filter narrows results."
    ),
)
def search_special_days(query: str, category: Category | None = None) -> str:
    if not query.strip():
        return "검색어를 입력해 주세요. (예: 고양이, 커피, 초콜릿)"
    return service.render_search(query, category)


@mcp.tool(
    annotations=ToolAnnotations(title="선물 추천", **_READ_ONLY),
    description=(
        "Recommends gifts from DayKeeper(데이키퍼) for a given occasion (a special day name like "
        "밸런타인데이, or a situation like 생일/100일/집들이), tailored to the relationship "
        "(partner/friend/parent/coworker/crush) and an optional budget range. Each suggestion "
        "includes the reason it fits, a price range, and a ready-made gift-shop search link so the "
        "user can act immediately."
    ),
)
def recommend_gifts(occasion: str, relationship: Relationship, budget: Budget | None = None) -> str:
    return service.render_gifts(occasion, relationship, budget)


@mcp.tool(
    annotations=ToolAnnotations(title="축하 메시지 생성", **_READ_ONLY),
    description=(
        "Generates three ready-to-send Korean celebration message drafts from DayKeeper(데이키퍼), "
        "tailored to the occasion, the relationship (partner/friend/parent/coworker/crush), and the "
        "tone (sweet/funny/polite/casual). Optionally prefixes the recipient's name. Useful right "
        "after finding a special day or picking a gift."
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
        "Calculates couple milestone anniversaries from DayKeeper(데이키퍼) based on the "
        "relationship start date (YYYY-MM-DD): how many days the couple has been together today "
        "(the start date counts as day 1, Korean convention), and the dates and D-day counts of "
        "upcoming 100-day milestones and yearly anniversaries. Pure calculation - nothing is stored."
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
        "Creates a one-stop celebration plan from DayKeeper(데이키퍼) for a date (defaults to today "
        "KST): what special day it is, gift ideas matched to the relationship and optional budget "
        "with gift-search links, and message drafts to send - combined into one actionable plan. "
        "If the date has no special day, the nearest upcoming one is used."
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
