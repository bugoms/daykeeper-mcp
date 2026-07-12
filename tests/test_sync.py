# -*- coding: utf-8 -*-
"""동기화 스크립트 파싱 로직 오프라인 테스트 (네트워크 호출 없음)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import sync_public_days as spd  # noqa: E402


def _resp(items):
    return json.dumps({
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {"items": items, "numOfRows": 1000, "pageNo": 1, "totalCount": 1},
        }
    })


def test_parse_list():
    raw = _resp({"item": [
        {"locdate": 20260216, "dateName": "설날", "isHoliday": "Y", "dateKind": "01", "seq": 1},
        {"locdate": 20260301, "dateName": "삼일절", "isHoliday": "Y", "dateKind": "01", "seq": 1},
    ]})
    assert len(spd.parse_response(raw)) == 2


def test_parse_single_item_dict():
    # 결과 1건이면 item이 배열이 아닌 단일 객체로 옴 (공공데이터 특유 형태)
    raw = _resp({"item": {"locdate": 20260101, "dateName": "1월1일", "isHoliday": "Y"}})
    items = spd.parse_response(raw)
    assert len(items) == 1 and items[0]["dateName"] == "1월1일"


def test_parse_empty_items():
    assert spd.parse_response(_resp("")) == []
    assert spd.parse_response(_resp({})) == []


def test_parse_error_code():
    raw = json.dumps({"response": {"header": {"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}}})
    with pytest.raises(RuntimeError):
        spd.parse_response(raw)


def test_parse_xml_key_error():
    raw = "<OpenAPI_ServiceResponse><cmmMsgHeader><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"
    with pytest.raises(spd.ApiKeyError):
        spd.parse_response(raw)


def test_normalize_skips_bad_rows():
    items = [
        {"locdate": 20260216, "dateName": " 설날 ", "isHoliday": "Y"},
        {"locdate": "bad", "dateName": "이상한 날"},
        {"locdate": 20260101, "dateName": ""},
    ]
    out = spd.normalize(items, "holiday")
    assert len(out) == 1
    assert out[0]["name"] == "설날" and out[0]["is_holiday"] is True


def test_dedup_kind_priority_and_holiday_or():
    entries = [
        {"year": 2026, "month": 3, "day": 1, "name": "삼일절", "kind": "national", "is_holiday": False},
        {"year": 2026, "month": 3, "day": 1, "name": "삼일절", "kind": "holiday", "is_holiday": True},
    ]
    merged = spd.dedup(entries)
    assert len(merged) == 1
    assert merged[0]["kind"] == "holiday" and merged[0]["is_holiday"] is True


def test_apply_enrichment():
    entries = [{"year": 2026, "month": 9, "day": 25, "name": "추석", "kind": "holiday", "is_holiday": True}]
    n = spd.apply_enrichment(entries, {"추석": {"care_point": "한가위", "gift_tags": ["fruit"], "place_query": None}})
    assert n == 1
    assert entries[0]["care_point"] == "한가위" and entries[0]["gift_tags"] == ["fruit"]
    assert "place_query" not in entries[0]  # null은 미적용
