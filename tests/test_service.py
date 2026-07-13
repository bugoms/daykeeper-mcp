# -*- coding: utf-8 -*-
"""핵심 로직 단위 테스트. 서버 기동 없이 순수 함수만 검증한다."""

from datetime import date

import pytest

from daykeeper import service
from daykeeper.dates import couple_milestones, dday_label, next_occurrence, parse_date, today_kst


# ---------------------------------------------------------------- 날짜 유틸

def test_today_kst_returns_date():
    assert isinstance(today_kst(), date)


def test_parse_date():
    assert parse_date("2026-08-08") == date(2026, 8, 8)
    with pytest.raises(ValueError):
        parse_date("2026/08/08")
    with pytest.raises(ValueError):
        parse_date("not-a-date")


def test_dday_label():
    today = date(2026, 7, 9)
    assert dday_label(date(2026, 7, 9), today) == "오늘"
    assert dday_label(date(2026, 7, 12), today) == "D-3"
    assert dday_label(date(2026, 7, 7), today) == "D+2"


def test_next_occurrence_year_boundary():
    today = date(2026, 12, 30)
    assert next_occurrence(1, 1, today) == date(2027, 1, 1)
    assert next_occurrence(12, 31, today) == date(2026, 12, 31)


def test_couple_milestones_korean_convention():
    # 2026-05-02 사귐(=1일째) → 2026-07-09는 69일째, 100일은 8/9
    start, today = date(2026, 5, 2), date(2026, 7, 9)
    days, milestones = couple_milestones(start, today, 3)
    assert days == 69
    assert milestones[0] == ("100일", date(2026, 8, 9))
    assert milestones[1] == ("200일", date(2026, 11, 17))


def test_couple_milestones_includes_today():
    start = date(2026, 1, 1)
    hundredth = date(2026, 4, 10)  # 1/1 + 99일
    days, milestones = couple_milestones(start, hundredth, 3)
    assert days == 100
    assert ("100일", hundredth) in milestones


# ---------------------------------------------------------------- 기념일 조회

def test_data_loaded():
    assert len(service.SPECIAL_DAYS) >= 80
    ids = [d["id"] for d in service.SPECIAL_DAYS]
    assert len(ids) == len(set(ids)), "중복 id 존재"


def test_days_for_aug_8_has_cat_and_grape():
    names = {d["id"] for d in service.days_for(8, 8)}
    assert {"cat-day", "grape-day"} <= names


def test_render_special_days_with_entries():
    out = service.render_special_days(date(2026, 8, 8), today=date(2026, 7, 9))
    assert "세계 고양이의 날" in out
    assert "포도데이" in out


def test_render_special_days_fallback_for_empty_date():
    # 1월 2일은 등록된 기념일이 없음 → 가까운 기념일 안내
    assert not service.days_for(1, 2)
    out = service.render_special_days(date(2026, 1, 2), today=date(2026, 1, 2))
    assert "가까운 챙길 만한 날" in out
    assert "세계 점자의 날" in out  # 1/4


def test_render_upcoming_year_boundary():
    out = service.render_upcoming(7, today=date(2026, 12, 30))
    assert "한 해의 마지막 날" in out
    assert "새해 첫날" in out


def test_search_cat_finds_both_cat_days():
    out = service.render_search("고양이", today=date(2026, 7, 9))
    assert "세계 고양이의 날" in out
    assert "일본 고양이의 날" in out


def test_search_no_result():
    out = service.render_search("존재하지않는키워드xyz")
    assert "찾지 못했어요" in out


# ---------------------------------------------------------------- 선물 추천

def test_recommend_gifts_valentines_partner():
    out = service.render_gifts("밸런타인데이", "partner", "10k_30k")
    assert "초콜릿" in out
    assert "gift.kakao.com/search/result?query=" in out


def test_recommend_gifts_link_is_url_encoded():
    out = service.render_gifts("밸런타인데이", "partner")
    assert "query=%EC" in out or "query=%EA" in out  # 한글이 인코딩됨
    # 원본 한글이 URL 안에 그대로 들어가지 않아야 함
    for line in out.splitlines():
        if "query=" in line:
            url = line.split("(")[-1].rstrip(")")
            assert all(ord(c) < 128 for c in url), f"인코딩 안 된 URL: {url}"


def test_recommend_gifts_unknown_occasion_falls_back():
    out = service.render_gifts("그냥 아무 날", "friend", "under_10k")
    # 태그 매칭이 없어도 관계·예산 기반 추천이 나와야 함
    assert out.count("- **") >= 3


def test_recommend_gifts_occasion_alias():
    out = service.render_gifts("여자친구 생일", "partner")
    assert "gift.kakao.com" in out


def test_pick_gifts_deterministic():
    a = service._pick_gifts(["chocolate"], "partner", "10k_30k")
    b = service._pick_gifts(["chocolate"], "partner", "10k_30k")
    assert [i["id"] for i in a] == [i["id"] for i in b]


# ---------------------------------------------------------------- 메시지

def test_messages_all_combinations_have_3_templates():
    for rel, tones in service.MESSAGES.items():
        for tone, templates in tones.items():
            assert len(templates) == 3, f"{rel}/{tone}"
            for t in templates:
                assert "{occasion}" in t, f"{rel}/{tone} 템플릿에 occasion 누락"


def test_render_messages_substitutes_occasion():
    out = service.render_messages("세계 고양이의 날", "friend", "funny")
    assert "세계 고양이의 날" in out
    assert "{occasion}" not in out


def test_render_messages_with_name():
    out = service.render_messages("밸런타인데이", "coworker", "polite", "민수")
    assert "민수님," in out


def test_josa_no_batchim_drops_copula():
    # '실버데이'(받침 없음) → '실버데이이래'가 아니라 '실버데이래'
    out = service.render_messages("실버데이", "partner", "casual")
    assert "실버데이이" not in out
    assert "실버데이래" in out or "실버데이라는데" in out


def test_josa_batchim_keeps_copula():
    # '핼러윈'(받침 있음) → '핼러윈이래' 유지
    out = service.render_messages("핼러윈", "friend", "casual")
    assert "핼러윈이래" in out


def test_josa_object_particle():
    # polite 톤의 '{occasion}을 맞아' → 받침 없으면 '를'
    out = service.render_messages("밸런타인데이", "coworker", "polite")
    assert "밸런타인데이를 맞아" in out
    out2 = service.render_messages("핼러윈", "coworker", "polite")
    assert "핼러윈을 맞아" in out2


# ---------------------------------------------------------------- 마일스톤·플랜

def test_render_milestones():
    out = service.render_milestones(date(2026, 5, 2), 3, today=date(2026, 7, 9))
    assert "69일째" in out
    assert "100일" in out
    assert "2026-08-09" in out


def test_render_milestones_future_start():
    out = service.render_milestones(date(2030, 1, 1), 3, today=date(2026, 7, 9))
    assert "미래 날짜" in out


def test_render_plan_on_special_day():
    out = service.render_plan(date(2026, 8, 8), "friend", today=date(2026, 8, 8))
    assert "챙김 플랜" in out
    assert "선물 아이디어" in out
    assert "메시지 초안" in out
    assert "{occasion}" not in out


def test_render_plan_empty_date_uses_nearest():
    out = service.render_plan(date(2026, 1, 2), "partner", today=date(2026, 1, 2))
    assert "가장 가까운" in out


# ---------------------------------------------------------------- 링크

def test_map_link_encoding():
    link = service.map_link("삼겹살 맛집")
    assert link.startswith("https://map.kakao.com/?q=")
    assert all(ord(c) < 128 for c in link)


# ---------------------------------------------------------------- 공공데이터 병합

def test_public_data_loaded():
    assert len(service.PUBLIC_ENTRIES) >= 200
    assert 2026 in service.PUBLIC_YEARS


def test_seollal_shows_as_holiday():
    # 2026 설날 연휴: 2/16~18
    out = service.render_special_days(date(2026, 2, 17), today=date(2026, 2, 1))
    assert "설날" in out
    assert "`공휴일`" in out
    assert "명절" in out  # enrichment care_point 적용


def test_public_dedup_by_alias():
    # 12/25: 큐레이션 '크리스마스'가 있으므로 공공 '기독탄신일'은 숨김
    out = service.render_special_days(date(2026, 12, 25), today=date(2026, 12, 1))
    assert "크리스마스" in out
    assert "기독탄신일" not in out
    # 5/1: '근로자의 날'(큐레이션) vs '노동절'(공공)
    out2 = service.render_special_days(date(2026, 5, 1), today=date(2026, 5, 1))
    assert "근로자의 날" in out2
    assert "노동절" not in out2


def test_public_dedup_same_name():
    # 어린이날은 양쪽에 동일 이름 존재 → 한 번만
    out = service.render_special_days(date(2026, 5, 5), today=date(2026, 5, 5))
    assert out.count("어린이날") == 1


def test_upcoming_includes_public_bokday():
    # 2026-07-15 초복 (잡절)
    out = service.render_upcoming(10, today=date(2026, 7, 9))
    assert "초복" in out
    assert "몸보신" in out


def test_search_finds_seollal_future_only():
    out = service.render_search("설날", today=date(2026, 7, 9))
    assert "설날" in out
    assert "찾지 못했어요" not in out
    assert "2/16" not in out or "D+" not in out  # 지난 날짜는 안 나옴


def test_gifts_for_chuseok_uses_enrichment_tags():
    out = service.render_gifts("추석", "parent")
    assert "gift.kakao.com" in out
    # premium_food/fruit/health_food 태그 계열 아이템이 상위에 나와야 함
    assert any(k in out for k in ("한우", "과일", "홍삼", "꿀", "샤인머스캣", "견과류"))


def test_gifts_for_bokday_has_map_link():
    out = service.render_gifts("초복", "coworker")
    assert "삼계탕" in out
    assert "map.kakao.com" in out


def test_plan_on_public_only_date():
    # 2026-09-25 추석 (큐레이션에는 없는 날)
    out = service.render_plan(date(2026, 9, 25), "parent", today=date(2026, 9, 25))
    assert "추석 챙김 플랜" in out
    assert "선물 아이디어" in out
    assert "{occasion}" not in out


def test_solar_term_generic_care():
    # 경칩(24절기, enrichment 없음) → 일반 문구
    out = service.render_search("경칩", today=date(2026, 1, 1))
    assert "24절기" in out


# ---------------------------------------------------------------- 공휴일 안내·대체공휴일

def test_substitute_holiday_badge_distinct():
    # 2026-03-02 대체공휴일(삼일절) → '대체공휴일' 배지로 공휴일과 구분
    out = service.render_special_days(date(2026, 3, 2), today=date(2026, 3, 2))
    assert "대체공휴일(삼일절)" in out
    assert "`대체공휴일`" in out
    # 원 공휴일(삼일절 3/1)은 '공휴일' 배지 유지... 큐레이션 삼일절이 우선이므로 3/1은 큐레이션 표기
    out2 = service.render_special_days(date(2026, 8, 17), today=date(2026, 8, 17))
    assert "`대체공휴일`" in out2  # 대체공휴일(광복절)


def test_nearest_holidays_prev_and_next():
    prev_h, next_h = service.nearest_holidays(date(2026, 9, 20))
    assert prev_h and prev_h[0] == date(2026, 8, 17)  # 대체공휴일(광복절)
    assert next_h and next_h[1]["name"] == "추석"


def test_holiday_footer_in_special_days():
    out = service.render_special_days(date(2026, 9, 20), today=date(2026, 9, 20))
    assert "다음 공휴일" in out
    assert "추석" in out
    assert "최근 지난 공휴일" in out


def test_holiday_footer_uses_canonical_name():
    # 12/20 기준 다음 공휴일은 기독탄신일(12/25) → 표시는 '크리스마스'
    out = service.render_special_days(date(2026, 12, 20), today=date(2026, 12, 20))
    assert "다음 공휴일" in out
    assert "기독탄신일" not in out
    assert "크리스마스" in out


def test_upcoming_footer_when_no_holiday_in_window():
    # 7/20~7/27에는 공휴일 없음 → 다음 공휴일(광복절) 안내 푸터
    out = service.render_upcoming(7, today=date(2026, 7, 20))
    assert "다음 공휴일" in out
    assert "광복절" in out


def test_search_holiday_keyword_lists_holidays():
    out = service.render_search("공휴일", today=date(2026, 9, 1))
    assert "찾지 못했어요" not in out
    assert "추석" in out


# ---------------------------------------------------------------- 선물 링크 보장

def test_special_days_with_gift_tags_include_gift_link():
    # 세계 고양이의 날(8/8): 챙김 포인트에 선물 언급 → 선물하기 링크 동반 필수
    out = service.render_special_days(date(2026, 8, 8), today=date(2026, 8, 8))
    assert "gift.kakao.com/search/result?query=" in out


def test_gifts_output_has_link_per_item_and_instruction():
    out = service.render_gifts("생일", "friend", "under_10k")
    items = out.count("- **")
    links = out.count("gift.kakao.com/search/result?query=")
    assert items >= 3 and links >= items  # 아이템마다 링크 1개 이상
    assert "반드시 함께 전달" in out


def test_plan_has_links_and_instruction():
    out = service.render_plan(date(2026, 9, 24), "parent", today=date(2026, 9, 24))
    assert out.count("gift.kakao.com") >= 2
    assert "반드시 함께 전달" in out


# ---------------------------------------------------- 사용 피드백 반영 (2026-07)

def test_special_days_multi_entry_note():
    # 8/8 포도데이+세계 고양이의 날 → 모두 알려주라는 안내 포함
    out = service.render_special_days(date(2026, 8, 8), today=date(2026, 8, 8))
    assert "모두 알려준 뒤" in out


def test_upcoming_from_future_start_crosses_year():
    # 12/20 기준 16일 조회 → 연말연시 경계를 넘어 새해 기념일까지
    out = service.render_upcoming(16, today=date(2026, 7, 13), start=date(2026, 12, 20))
    assert "2026-12-20부터 16일 안" in out
    assert "크리스마스" in out
    assert "새해 첫날" in out


def test_upcoming_default_scope_unchanged():
    out = service.render_upcoming(7, today=date(2026, 7, 13))
    assert "오늘부터 7일 안" in out


def test_upcoming_has_gift_nudge():
    out = service.render_upcoming(7, today=date(2026, 7, 13))
    assert "recommend_gifts" in out
    assert "반드시 함께 전달" in out


def test_milestones_annotate_coinciding_special_day():
    # 시작일 2026-09-17 → 100일째가 2026-12-25 (크리스마스)
    out = service.render_milestones(date(2026, 9, 17), 1, today=date(2026, 10, 1))
    assert "2026-12-25" in out
    assert "같은 날: 크리스마스" in out
