# -*- coding: utf-8 -*-
"""기념일 데이터 커버리지 검사: 365일 중 직접 커버되는 날과 최대 공백 구간을 보고."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from daykeeper import service  # noqa: E402

covered = {(d["month"], d["day"]) for d in service.SPECIAL_DAYS}
pub_2026 = {(p["month"], p["day"]) for p in service.PUBLIC_ENTRIES if p["year"] == 2026}
print(f"큐레이션 엔트리: {len(service.SPECIAL_DAYS)}건, 공공데이터 엔트리: {len(service.PUBLIC_ENTRIES)}건 (연도: {service.PUBLIC_YEARS})")
print(f"큐레이션만 커버: {len(covered)}/366일 → 공공데이터 포함(2026): {len(covered | pub_2026)}/366일")
covered = covered | pub_2026

# 최대 공백 구간 계산 (평년 기준)
gaps = []
current_gap = 0
gap_start = None
d = date(2026, 1, 1)
max_gap, max_range = 0, None
while d.year == 2026:
    if (d.month, d.day) in covered:
        if current_gap > max_gap:
            max_gap, max_range = current_gap, (gap_start, d - timedelta(days=1))
        current_gap = 0
    else:
        if current_gap == 0:
            gap_start = d
        current_gap += 1
    d += timedelta(days=1)
if current_gap > max_gap:
    max_gap, max_range = current_gap, (gap_start, d - timedelta(days=1))

print(f"최대 공백 구간: {max_gap}일", f"({max_range[0]} ~ {max_range[1]})" if max_range else "")
print("※ 공백일은 서비스 로직이 '가까운 기념일 안내'로 fallback 처리하므로 빈 응답은 없음")

# 태그 무결성: special_days의 gift_tags가 gifts.json 아이템에 존재하는지
item_tags = {t for i in service.GIFT_ITEMS for t in i["tags"]}
missing = set()
for e in service.SPECIAL_DAYS:
    for t in e["gift_tags"]:
        if t not in item_tags:
            missing.add(f"{e['id']}:{t}")
occ_missing = {f"{k}:{t}" for k, tags in service.OCCASION_TAGS.items() for t in tags if t not in item_tags}
if missing or occ_missing:
    print("⚠️ 선물 아이템이 없는 태그:", sorted(missing | occ_missing))
    sys.exit(1)
print("태그 무결성: OK (모든 gift_tags에 대응하는 선물 아이템 존재)")
