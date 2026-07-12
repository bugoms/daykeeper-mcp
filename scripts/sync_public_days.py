# -*- coding: utf-8 -*-
"""KASI 특일 정보 API(공공데이터포털) 동기화 → src/daykeeper/data/public_days.json 생성.

빌드 타임 전용 스크립트. 런타임 서버는 이 스크립트가 생성한 JSON만 읽는다.
사용법:  python scripts/sync_public_days.py   (.env의 KASI_SERVICE_KEY 사용)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "src" / "daykeeper" / "data"
OUT_PATH = DATA_DIR / "public_days.json"
ENRICH_PATH = DATA_DIR / "public_enrichment.json"

BASE = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService"

# (오퍼레이션, kind) — dedup 시 앞쪽이 우선
OPS = [
    ("getRestDeInfo", "holiday"),
    ("getHoliDeInfo", "national"),
    ("getAnniversaryInfo", "anniversary"),
    ("get24DivisionsInfo", "solar_term"),
    ("getSundryDayInfo", "sundry"),
]
KIND_PRIORITY = {k: i for i, (_, k) in enumerate(OPS)}


class ApiKeyError(RuntimeError):
    pass


def load_env_key() -> str:
    key = os.environ.get("KASI_SERVICE_KEY", "").strip()
    if not key:
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("KASI_SERVICE_KEY=") and not line.startswith("#"):
                    key = line.split("=", 1)[1].strip()
    if not key or "여기에" in key:
        sys.exit("KASI_SERVICE_KEY가 없습니다. .env 파일에 인증키를 넣어 주세요.")
    return key


def parse_response(raw: str, op: str = "?", year: int = 0) -> list[dict]:
    """공공데이터 응답 파싱. 단건 응답(item이 dict), 빈 응답, XML 에러 모두 처리."""
    if raw.lstrip().startswith("<"):
        if "SERVICE" in raw.upper() and "KEY" in raw.upper():
            raise ApiKeyError(f"{op}/{year}: 인증키 오류 — {raw[:200]}")
        raise RuntimeError(f"{op}/{year}: XML 에러 응답 — {raw[:200]}")
    data = json.loads(raw)
    header = data["response"]["header"]
    if str(header.get("resultCode")) not in ("00", "0"):
        raise RuntimeError(f"{op}/{year}: {header.get('resultCode')} {header.get('resultMsg')}")
    items = data["response"]["body"].get("items") or {}
    if not isinstance(items, dict):
        return []
    item = items.get("item")
    if item is None:
        return []
    if isinstance(item, dict):
        item = [item]
    return item


def normalize(items: list[dict], kind: str) -> list[dict]:
    out = []
    for it in items:
        loc = str(it.get("locdate", "")).strip()
        name = str(it.get("dateName", "")).strip()
        if len(loc) != 8 or not loc.isdigit() or not name:
            continue
        out.append(
            {
                "year": int(loc[:4]),
                "month": int(loc[4:6]),
                "day": int(loc[6:8]),
                "name": name,
                "kind": kind,
                "is_holiday": str(it.get("isHoliday", "N")).strip().upper() == "Y",
            }
        )
    return out


def dedup(entries: list[dict]) -> list[dict]:
    """(날짜, 이름) 동일 항목 병합 — kind는 우선순위 높은 쪽, is_holiday는 OR."""
    merged: dict[tuple, dict] = {}
    for e in entries:
        k = (e["year"], e["month"], e["day"], e["name"])
        if k in merged:
            old = merged[k]
            old["is_holiday"] = old["is_holiday"] or e["is_holiday"]
            if KIND_PRIORITY[e["kind"]] < KIND_PRIORITY[old["kind"]]:
                old["kind"] = e["kind"]
        else:
            merged[k] = dict(e)
    return sorted(merged.values(), key=lambda e: (e["year"], e["month"], e["day"], KIND_PRIORITY[e["kind"]], e["name"]))


def apply_enrichment(entries: list[dict], enrichment: dict) -> int:
    count = 0
    for e in entries:
        enr = enrichment.get(e["name"])
        if enr:
            for field in ("care_point", "gift_tags", "place_query"):
                if enr.get(field):
                    e[field] = enr[field]
            count += 1
    return count


def _fetch(op: str, year: int, key: str) -> list[dict]:
    params = {"solYear": str(year), "ServiceKey": key, "_type": "json", "numOfRows": "1000"}
    url = f"{BASE}/{op}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8")
    return parse_response(raw, op, year)


def fetch_year(op: str, year: int, key: str) -> list[dict]:
    """포털 개편으로 키가 1개만 발급됨 — 실패 시 디코딩 형태로 자동 재시도."""
    try:
        return _fetch(op, year, key)
    except ApiKeyError:
        alt = urllib.parse.unquote(key)
        if alt != key:
            print(f"  ! 키 형태 재시도 (디코딩 형태): {op}/{year}")
            return _fetch(op, year, alt)
        raise


def main() -> None:
    key = load_env_key()
    enrichment = json.loads(ENRICH_PATH.read_text(encoding="utf-8")) if ENRICH_PATH.exists() else {}
    this_year = date.today().year
    years = [this_year, this_year + 1]

    all_entries: list[dict] = []
    years_ok: list[int] = []
    for year in years:
        year_entries: list[dict] = []
        for op, kind in OPS:
            items = fetch_year(op, year, key)
            got = normalize(items, kind)
            year_entries.extend(got)
            print(f"  {year} {op}: {len(got)}건")
        if not year_entries:
            print(f"⚠️ {year}년 데이터 없음 (차차년도는 6~8월 이후 제공) — 건너뜀")
            continue
        holidays = [e for e in year_entries if e["is_holiday"]]
        if len(holidays) < 5:
            print(f"⚠️ {year}년 공휴일이 {len(holidays)}건뿐 — 데이터 이상 의심, 해당 연도 제외")
            continue
        years_ok.append(year)
        all_entries.extend(year_entries)

    if not years_ok:
        sys.exit("유효한 연도 데이터가 없어 기존 파일을 유지합니다.")

    merged = dedup(all_entries)
    enriched = apply_enrichment(merged, enrichment)

    payload = {"synced_at": date.today().isoformat(), "years": years_ok, "days": merged}
    tmp = OUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT_PATH)

    kinds = {}
    for e in merged:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"\n저장: {OUT_PATH}")
    print(f"연도: {years_ok} / 총 {len(merged)}건 (enrichment {enriched}건 적용)")
    print("종류별:", ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))


if __name__ == "__main__":
    main()
