# DayKeeper (데이키퍼)

사소하지만 챙기면 빛나는 기념일을 찾아, 관계·예산에 맞는 선물과 메시지까지 제안하는 MCP 서버.

"오늘 무슨 날이야?"에서 시작해 **기념일 조회 → 선물 추천(검색 링크 포함) → 보낼 메시지 초안**까지 행동으로 이어줍니다.

## Tools (7)

| Tool | 설명 |
|---|---|
| `get_special_days` | 특정 날짜(기본: 오늘 KST)의 기념일 조회. 없으면 가까운 기념일 안내 |
| `get_upcoming_special_days` | 향후 N일 내 기념일 타임라인 + D-day |
| `search_special_days` | 키워드/카테고리로 기념일 검색 (예: 고양이, 커피) |
| `recommend_gifts` | 상황 × 관계 × 예산 기반 선물 추천 + 선물 검색 링크 |
| `generate_celebration_message` | 관계 × 톤별 바로 보낼 수 있는 메시지 초안 3종 |
| `calc_couple_milestones` | 사귄 날짜 기준 100일 단위·주년 마일스톤 D-day 계산 |
| `create_celebration_plan` | 기념일 + 선물 + 메시지를 하나로 묶은 원스톱 챙김 플랜 |

## 기술 스펙

- **전송**: MCP Streamable HTTP (경로 `/mcp`), Stateless
- **런타임**: Python 3.12 + 공식 MCP SDK (FastMCP)
- **데이터**: 내장 JSON 2종 (런타임 외부 API 호출 없음 — 전 툴 수 ms 응답)
  - 큐레이션 기념일 88건 (재미있는 날, 매월 14일 시리즈 등)
  - 공공데이터 302건 — 설날·추석 연휴, 대체공휴일, 24절기, 삼복 등 연도별 가변 특일 (출처: 한국천문연구원 특일 정보, 공공데이터포털)
- **시간대**: Asia/Seoul (KST) 고정
- **헬스체크**: `GET /health`

### 공공데이터 갱신 (빌드 타임)

```bash
# .env에 KASI_SERVICE_KEY 설정 후 (공공데이터포털에서 발급, .env.example 참고)
python scripts/sync_public_days.py   # → src/daykeeper/data/public_days.json 재생성
```

서버는 생성된 JSON만 읽으므로 배포 환경에 API 키가 필요 없습니다.

## 로컬 실행

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # Windows
.venv/Scripts/python -m daykeeper.server
# → http://127.0.0.1:8080/mcp (Streamable HTTP)
```

테스트:

```bash
.venv/Scripts/python -m pytest
```

## Docker

```bash
docker build -t daykeeper .
docker run -p 8080:8080 daykeeper
```

`PORT` 환경변수로 포트 변경 가능 (기본 8080).
