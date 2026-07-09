# -*- coding: utf-8 -*-
"""E2E 검증: Streamable HTTP로 서버에 접속해 initialize → tools/list → tools/call 수행."""

import asyncio
import io
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123/mcp"
REQUIRED_ANNOTATIONS = ["title", "readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"]


async def main() -> None:
    out = io.open("scripts/e2e_result.txt", "w", encoding="utf-8")

    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            out.write(f"[initialize] server={init.serverInfo.name} protocol={init.protocolVersion}\n")
            assert "kakao" not in init.serverInfo.name.lower(), "server name contains 'kakao'"

            tools = (await session.list_tools()).tools
            out.write(f"[tools/list] {len(tools)} tools\n")
            assert len(tools) == 7, f"expected 7 tools, got {len(tools)}"
            for t in tools:
                assert "kakao" not in t.name.lower(), f"tool name contains kakao: {t.name}"
                assert t.description and len(t.description) <= 1024
                assert "DayKeeper" in t.description, f"{t.name}: description missing service name"
                assert t.annotations is not None, f"{t.name}: missing annotations"
                for field in REQUIRED_ANNOTATIONS:
                    assert getattr(t.annotations, field, None) is not None, f"{t.name}: annotations.{field} unset"
                out.write(f"  - {t.name}: annotations OK\n")

            calls = [
                ("get_special_days", {"date": "2026-08-08"}),
                ("get_special_days", {}),
                ("get_upcoming_special_days", {"days": 14}),
                ("search_special_days", {"query": "고양이"}),
                ("recommend_gifts", {"occasion": "밸런타인데이", "relationship": "partner", "budget": "10k_30k"}),
                ("generate_celebration_message", {"occasion": "세계 커피의 날", "relationship": "friend", "tone": "funny"}),
                ("calc_couple_milestones", {"start_date": "2026-05-02"}),
                ("create_celebration_plan", {"relationship": "partner", "date": "2026-07-14"}),
            ]
            for name, args in calls:
                result = await session.call_tool(name, args)
                assert not result.isError, f"{name} returned error: {result.content}"
                text = result.content[0].text
                assert len(text) > 20, f"{name}: suspiciously short response"
                out.write(f"\n===== {name}({args}) =====\n{text}\n")

    out.write("\nE2E OK\n")
    out.close()
    print("E2E OK")


asyncio.run(main())
