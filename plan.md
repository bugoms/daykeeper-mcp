# 기념일 챙김 MCP 서버 — 구현 계획

> **공모전**: 카카오 Agentic Player 10 (예선 마감 **2026-07-14**, 오늘 기준 **D-5**)
> **컨셉**: "오늘 무슨 날인지"에서 끝나지 않고, **관계 × 예산 기반 선물 추천 + 메시지 문구 생성**까지 행동으로 이어주는 기념일 챙김 도우미

---

## 1. 프로젝트 개요

| 항목             | 내용                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------ |
| 서버 이름 (가칭) | **DayKeeper (데이키퍼)** — ⚠️ "kakao" 포함 금지 규칙 준수                                                                |
| 한 줄 소개       | 사소하지만 챙기면 빛나는 기념일을 찾아, 관계·예산에 맞는 선물과 메시지까지 제안하는 MCP                                  |
| 타겟 시나리오    | "오늘 뭐 특별한 날이야?" → "세계 고양이의 날! 고양이 좋아하는 친구에게 츄르 세트 어때요? 보낼 메시지도 만들어 드릴게요." |
| 차별점           | 뻔한 법정기념일이 아닌 **재미있는 날**(고양이의 날, 삼겹살데이, 매월 14일 시리즈 등) + **관계 기반 행동 추천**           |

### MVP 범위

**포함:**

- 날짜별 기념일 조회 (오늘/특정일/다가오는 날)
- 키워드·카테고리로 기념일 검색
- 기념일 × 관계(연인/친구/부모님/동료) × 예산별 선물 추천 (선물하기 **검색 키워드** 제공)
- 관계·톤별 축하 메시지 문구 생성
- 연인 마일스톤 계산 (100일, 1주년 등 D-day)
- **바로 열리는 "행동 링크" 제공**: 선물 추천에는 선물하기 검색 결과 링크(`https://gift.kakao.com/search/result?query=…`), 장소 맥락이 있는 기념일(음식 데이, 데이트형 기념일 등)에는 카카오맵 검색 결과 링크(`https://map.kakao.com/?q=…`)를 함께 반환 — 클릭 한 번으로 **검색이 이미 완료된 화면**에 도달. 단순 URL 조합이라 API·인증 불필요, 응답속도 영향 없음

**제외 (본선/추후):**

- 선물하기 결제·상품 API 직접 연동 (공식 API 미공개 — 검색 키워드 + 검색 결과 링크로 대체)
- 사용자별 기념일 저장 (Stateless 권장 + OAuth 구현 시간 부족 → 파라미터로 받는 방식으로 대체)
- 위젯 JSON 응답 (마크다운 텍스트로 충분)

---

## 2. 심사 기준 매핑 (반려 방지)

개발가이드(2026-06-12판) 필수 사항 → 이 프로젝트의 대응:

| 심사 기준                                         | 대응                                                                                                |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| MCP 스펙 2025-03-26 ~ 2025-11-25                  | 공식 Python SDK 최신 버전 사용                                                                      |
| **Streamable HTTP 전용**                          | FastMCP `transport="streamable-http"`                                                               |
| Remote 공개 URL                                   | PlayMCP in KC 배포로 자동 충족                                                                      |
| Stateless 권장                                    | `stateless_http=True`, 세션·저장소 없음                                                             |
| 서버명/툴명 "kakao" 금지                          | 서버명 DayKeeper, 툴명 전부 영문 일반어                                                             |
| 툴 3~10개 권장                                    | **7개** (아래 설계)                                                                                 |
| name/description/inputSchema/**annotations** 필수 | 모든 툴에 annotations 5종(title, readOnlyHint, destructiveHint, openWorldHint, idempotentHint) 명시 |
| description 영문 + 서비스명 병기 + 1,024자 이내   | 예: `"Retrieves special days ... from DayKeeper(데이키퍼)"`                                         |
| 응답 평균 100ms, p99 3,000ms                      | **외부 API 호출 없음** — 전부 내장 JSON 데이터 조회 (수 ms)                                         |
| API raw 응답 금지, 정제된 마크다운                | 응답을 마크다운 텍스트로 직접 구성                                                                  |
| MCP Inspector 사전 점검                           | 배포 전 필수 체크 단계에 포함                                                                       |
| 광고 유도 금지                                    | 특정 브랜드 언급 없이 카테고리·키워드만 추천                                                        |

---

## 3. 아키텍처 & 기술 스택

```
[PlayMCP AI채팅 / MCP 클라이언트]
        │  Streamable HTTP (POST /mcp)
        ▼
[FastMCP 서버 (stateless)] ─ Python 3.12 + mcp SDK + uvicorn
        │
        ▼
[내장 데이터 (JSON, 앱 시작 시 메모리 로드)]
  ├─ special_days.json   (기념일 DB, 300+건)
  ├─ gifts.json          (관계×예산 선물 매트릭스)
  └─ messages.json       (관계×톤 메시지 템플릿)
```

- **언어/프레임워크**: Python 3.12 + 공식 `mcp` SDK(FastMCP) — 개발 속도 최우선. (대안: TypeScript SDK)
- **데이터**: 외부 API·DB 없이 **레포에 포함된 정적 JSON**. 응답속도 요건을 확실히 충족하고 장애 요인 제거.
- **시간대**: 서버는 UTC로 돌 수 있으므로 "오늘" 계산은 **반드시 `Asia/Seoul` 고정** (`zoneinfo`).
- **포트**: `PORT` 환경변수 우선, 기본 8080. `/health` GET 엔드포인트 추가 (KC 헬스체크 대비).
- **배포**: GitHub public 레포 + 루트 Dockerfile → **PlayMCP in KC "Git 소스 빌드"** (레지스트리 인증·amd64 이슈가 없어 컨테이너 방식보다 단순. KC 공식 가이드도 Dockerfile 있는 레포는 Git 소스 빌드를 권장).
- **KC 서버 이름 규칙**: PlayMCP in KC의 서버 이름은 **Kubernetes DNS 네이밍 규칙**을 따라야 함 — 소문자 영문·숫자·하이픈만, 시작/끝은 영숫자 → `daykeeper`로 등록 (PlayMCP 콘솔에 노출되는 서비스명과는 별개).

---

## 4. 툴 설계 (7개)

모든 툴 공통: `readOnlyHint=true`, `destructiveHint=false`, `openWorldHint=false`(내장 데이터만 사용), `idempotentHint=true`(입력 동일 → 출력 동일하게 결정적으로 구현). description은 영문, `DayKeeper(데이키퍼)` 포함.

### 4.1 `get_special_days` — 날짜별 기념일 조회

- **input**: `date` (string, `YYYY-MM-DD`, optional — 생략 시 오늘 KST)
- **output**: 해당 날짜의 기념일 목록 (이름, 카테고리, 유래 한 줄, 챙김 포인트) 마크다운. 장소 맥락이 있는 기념일(`place_query` 보유)은 카카오맵 검색 링크 첨부
- 핵심 툴. 기념일 없는 날이 없도록 데이터 커버리지 확보 (§5)

### 4.2 `get_upcoming_special_days` — 다가오는 기념일

- **input**: `days` (int, 1~30, default 7), `category` (enum, optional)
- **output**: 향후 N일 내 기념일 타임라인 + 각각 D-day

### 4.3 `search_special_days` — 기념일 검색

- **input**: `query` (string — 키워드 예: "고양이", "커피", "초콜릿"), `category` (optional)
- **output**: 매칭 기념일 목록 (날짜, D-day 포함)
- "고양이 관련 기념일 언제야?" 같은 질의 대응

### 4.4 `recommend_gifts` — 선물 추천

- **input**: `occasion` (string — 기념일명 또는 상황), `relationship` (enum: `partner`/`friend`/`parent`/`coworker`/`crush`), `budget` (enum: `under_10k`/`10k_30k`/`30k_50k`/`over_50k`, optional)
- **output**: 관계·예산별 선물 3~5개 — 각각 [선물명, 추천 이유, 예상 가격대, **선물하기 검색 키워드 + 검색 결과 링크**]. 외식·나들이형 추천에는 카카오맵 검색 링크 병행
- ⚠️ 특정 브랜드·상품명 대신 카테고리+키워드 (광고 유도 금지 대응). 링크는 특정 상품/업체가 아닌 **검색 결과 화면**으로만 연결 — 광고가 아닌 편의 기능으로 유지

### 4.5 `generate_celebration_message` — 메시지 문구 생성

- **input**: `occasion` (string), `relationship` (enum, 위와 동일), `tone` (enum: `sweet`/`funny`/`polite`/`casual`, default casual), `recipient_name` (string, optional)
- **output**: 바로 복사해 보낼 수 있는 메시지 초안 2~3개 (템플릿 + 상황 변수 조합, 결정적 생성)

### 4.6 `calc_couple_milestones` — 연인 마일스톤 계산

- **input**: `start_date` (string, `YYYY-MM-DD` — 사귄 날), `count` (int, default 5)
- **output**: 오늘 기준 며칠째인지 + 다가오는 마일스톤(100일 단위, n주년) 날짜와 D-day
- 순수 날짜 계산이라 저장 없이 Stateless 유지 가능

### 4.7 `create_celebration_plan` — 원스톱 챙김 플랜

- **input**: `date` (optional), `relationship` (enum), `budget` (enum, optional)
- **output**: [오늘의 기념일 → 추천 선물 → 보낼 메시지]를 하나의 마크다운 플랜으로 종합
- 내부적으로 4.1 + 4.4 + 4.5 로직 재사용. 데모·심사에서 임팩트를 주는 대표 툴

---

## 5. 데이터 설계

### 5.1 `special_days.json` — 기념일 DB (목표 300+건, 365일 커버)

```json
{
  "id": "world-cat-day",
  "name": "세계 고양이의 날",
  "name_en": "International Cat Day",
  "month": 8,
  "day": 8,
  "category": "animal", // official | fun | food | animal | love | culture | monthly14
  "origin": "고양이 보호 인식을 위해 IFAW가 2002년 제정",
  "care_point": "고양이 키우는/좋아하는 사람에게 안부+간식 선물 찬스",
  "gift_tags": ["cat", "pet_snack", "character"],
  "place_query": null // 장소 맥락이 있으면 카카오맵 검색어 (예: 삼겹살데이 → "삼겹살 맛집")
}
```

**데이터 소스 — "기념일은 어떻게 알아내나? API가 있나?"**

- 결론: **런타임에 호출하는 기념일 API는 쓰지 않는다.** "고양이의 날, 삼겹살데이" 같은 재미있는 날을 한국어로 제공하는 무료 공개 API는 사실상 없고, 있다 해도 런타임 외부 호출은 응답속도 요건(평균 100ms)과 장애 리스크 때문에 배제.
- 대신 **빌드 타임에 한 번 수집·검증해서 정적 JSON으로 굳힌다**:
  1. **한국천문연구원 특일 정보 API** (공공데이터포털 data.go.kr, 무료) — 법정 국경일·공휴일·기념일을 시드로 수집. 유일하게 쓸 만한 공식 API지만 "재미있는 날"은 없음
  2. 매월 14일 시리즈·음식 데이(삼겹살데이 등) — 위키백과 등 공개 목록 기반 수동 큐레이션
  3. "세계 ○○의 날" — UN 국제 기념일 공식 목록(un.org) 참조
  4. 나머지는 LLM으로 초안 대량 생성 후 **상위 50개 유명 기념일은 날짜를 교차 검증** (틀린 날짜가 서비스 신뢰도를 깎는 최대 리스크)
- 월/일 고정 기념일만 다루므로 연도가 바뀌어도 유지보수 부담 없음 (음력 기반 날은 MVP 제외)

**카테고리 구성 전략** (LLM으로 초안 생성 → 주요 날짜만 수동 검증):

- 매월 14일 시리즈 (다이어리데이, 발렌타인, 화이트, 블랙, 로즈, 키스, 실버, 그린, 포토, 와인, 무비, 허그) — 12건
- 음식 데이(삼겹살데이 3/3, 치킨데이, 빼빼로데이 11/11 등), 동물 데이(고양이 8/8, 강아지 등)
- 세계 ○○의 날 (커피 10/1, 친구 7/30, 미소 등 UN·국제 기념일)
- 한국 법정·계기 기념일 중 선물 맥락이 있는 것 (어버이날, 스승의날 등)
- **빈 날짜 채우기**: 데이터 생성 후 365일 커버리지 검사 스크립트 실행 → 빈 날은 "매달 반복" 규칙(매월 14일 등)이나 근접 기념일 안내로 보완

### 5.2 `gifts.json` — 선물 매트릭스

`gift_tags × relationship × budget` → 선물 아이템. 각 아이템: `name`(일반명), `reason`, `price_range`, `search_keywords[]`. 태그당 관계 4종 × 예산 4종을 다 채우지 않고, 관계·예산별 **fallback 공통 추천**을 두어 데이터량 관리.

### 5.3 `messages.json` — 메시지 템플릿

`relationship × tone` 별 템플릿 3개 이상. `{name}`, `{occasion}`, `{care_point}` 변수 치환. 입력이 같으면 같은 출력이 나오도록 결정적으로 선택(idempotentHint=true 유지).

---

## 6. 프로젝트 구조

```
kakaomcp/
├── plan.md
├── Dockerfile                  # 루트 필수 (KC Git 소스 빌드)
├── pyproject.toml
├── README.md                   # PlayMCP 등록 정보 초안 겸용
├── src/
│   └── daykeeper/
│       ├── server.py           # FastMCP 앱 + 툴 정의 + annotations
│       ├── service.py          # 조회/추천/생성 로직 (순수 함수)
│       ├── dates.py            # KST 오늘, D-day, 마일스톤 계산
│       └── data/
│           ├── special_days.json
│           ├── gifts.json
│           └── messages.json
├── scripts/
│   └── check_coverage.py       # 365일 기념일 커버리지 검사
└── tests/
    └── test_service.py         # 핵심 로직 단위 테스트
```

**Dockerfile 골자**: `python:3.12-slim` → 의존성 설치 → `EXPOSE 8080` → `CMD uvicorn ...` (PORT env 대응)

---

## 7. 일정 (D-day 기준, 심사 소요 1~2영업일 감안)

| 날짜                  | 목표                                                                                                                                                                                                           |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **7/9 (목) D-5**      | 스캐폴딩 + 데이터 3종 구축(LLM 생성→검증) + 툴 7개 구현 + 단위 테스트                                                                                                                                          |
| **7/10 (금) D-4**     | **오전**: MCP Inspector 전 항목 점검, Dockerfile 로컬 빌드 확인 → GitHub push → KC Git 빌드 배포, Endpoint 확보 → PlayMCP **임시 등록** → AI채팅 실사용 테스트 → **금요일 중 심사 요청** (주말 전 접수가 핵심) |
| 7/11~13 (토~월) D-3~1 | 반려 시 사유 수정 → 재배포(같은 서버 이름으로 재생성) → 재심사. 승인 시 **"전체 공개" 전환** + 상세페이지 URL 확보                                                                                             |
| **7/14 (화) D-0**     | 공모전 페이지 비즈폼으로 예선 접수 완료                                                                                                                                                                        |

> 심사가 영업일 기준이므로 **금요일(7/10) 심사 요청이 사실상 마지노선**. 7/9~10 이틀에 개발을 끝내는 것이 이 계획의 전부다.

---

## 8. 테스트 계획

1. **단위 테스트**: 날짜 계산(KST, 윤년, 연말 경계), 커버리지(365일 모두 응답 존재), 추천 fallback
2. **MCP Inspector**: initialize/tools-list/tools-call 전 툴 호출, annotations 노출 확인, Streamable HTTP 연결 확인
3. **로컬 Docker**: `docker build` + `docker run` 후 Inspector로 컨테이너 대상 재검증
4. **PlayMCP "정보 불러오기"**: 실패 시 서버 스펙 문제이므로 즉시 디버깅
5. **PlayMCP AI채팅 시나리오 테스트**:
   - "오늘 무슨 날이야?" / "이번 주에 챙길 만한 날 있어?"
   - "여자친구한테 3만원대 선물 추천해줘" / "보낼 메시지도 써줘"
   - "우리 5월 2일에 사귀었는데 200일 언제야?"
   - "고양이 관련 기념일 알려줘"
   - 응답에 포함된 선물하기/카카오맵 링크가 실제 검색 결과로 정상 연결되는지 클릭 확인 (한글 검색어 URL 인코딩 검증)

---

## 9. 리스크 & 대응

| 리스크                           | 대응                                                                                                               |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 심사 반려로 일정 초과            | 금요일 오전 심사 요청 목표. 반려 사유 최다 후보(annotations 누락, description 규칙)는 §2 체크리스트로 사전 차단    |
| KC 포트/헬스체크 스펙 불명확     | PORT env 대응 + `/health` 엔드포인트 + 배포 후 Starting에서 멈추면 로그 없이도 원인 추정 가능하도록 즉시 응답 구조 |
| "정보 불러오기" 실패             | 배포 전 Inspector + 로컬 Docker 검증으로 사전 재현                                                                 |
| 기념일 데이터 빈약/오류          | 커버리지 스크립트 + 상위 50개 유명 기념일 수동 검증                                                                |
| Stateless라 개인화 부족          | 마일스톤 계산 툴(입력 기반)로 개인화 경험 제공. 본선에서 OAuth+저장 확장 어필                                      |
| description에 카카오 브랜드 언급 | 툴명·서버명은 금지 확정이므로 배제. description도 "gift service search keywords" 등 중립 표현 사용                 |

---

## 10. 본선 대비 확장 아이디어 (접수 후)

- OAuth 인증 + 사용자별 기념일/받는 사람 프로필 저장 → 자동 리마인드
- 선물 히스토리 기반 중복 방지 추천
- 시즌 큐레이션 (발렌타인·빼빼로·크리스마스 스페셜)
- 기업용: 팀원 생일/기념일 챙김 봇
- 위젯 JSON 응답으로 선물 카드 UI 제공

---

## 11. 즉시 시작할 작업 (오늘)

1. `pyproject.toml` + FastMCP 스캐폴딩 (stateless streamable-http, /health)
2. 기념일 데이터 300건 생성 + 커버리지 검사
3. 선물 매트릭스·메시지 템플릿 데이터 생성
4. 툴 7개 구현 (annotations 포함)
5. Dockerfile + 로컬 Docker 검증
6. GitHub 레포 생성·push

---

## 12. 참고 — PlayMCP in KC 요약 (공식 AI용 문서 기반)

PlayMCP in KC(https://playmcp.kakaocloud.io)는 카카오클라우드의 MCP 서버 호스팅 포털. Endpoint URL을 발급받아 PlayMCP 콘솔(https://playmcp.kakao.com/console)에 등록하는 구조.

**이용 흐름**: 로그인 → My MCP → 새 MCP 서버 등록(Git 소스 빌드 또는 컨테이너 이미지) → Active 대기 → 상세 페이지에서 Endpoint URL 복사 → PlayMCP 콘솔에 등록

**배포 방식 선택 기준** (공식 권장):
- Dockerfile 있는 Git 레포 보유 → **Git 소스 빌드** (Git URL, 브랜치/ref, Dockerfile 경로 선택, private HTTPS 레포는 PAT)
- 레지스트리에 이미지 push 완료 → **컨테이너 이미지** (레지스트리 호스트, 이미지명, 태그, private면 자격증명)

**API 엔트리포인트** (자동화·상태 확인 시 활용 가능):
- `GET /api/v2/mcp/my-mcp-servers` — 내 MCP 서버 목록 조회
- `POST /api/v2/mcp/builder/image-mcp-servers` — 이미지 방식 서버 등록
- AI용 가이드 문서: `/ai/guide.md`

**주의사항**:
- 서버 이름은 Kubernetes DNS 네이밍 규칙 준수 (소문자·숫자·하이픈)
- PAT·레지스트리 비밀번호 등 시크릿은 **포털에서만 직접 입력** — 프롬프트/채팅에 노출 금지 (본 프로젝트는 public 레포라 해당 없음)
