# 채용공고 자동 수집 봇 — 설계서 v3

작성일: 2026-04-28
대상: Leo (zxcklwe@gmail.com)

---

## 0. 요구사항 요약

- **직군**: 백엔드 / 풀스택 개발자 (Python, Java, Node.js, Spring 등)
- **경력**: 주니어 (1~3년, 신입 포함 선택 가능)
- **지역**: 서울 / 수도권 (경기, 인천)
- **사이트**: 원티드, 사람인, 잡코리아
- **실행 주기**: 매일 오전 9시 (로컬 Mac cron)
- **전달 방식**: Discord 웹훅 — Top N 공고를 개별 메시지로 발송
- **AI 랭킹**: `claude -p` CLI로 이력서 기반 Top N 추출 (실패 시 키워드 점수 fallback)

---

## 1. 실행 환경과 트리거

로컬 Mac에서 cron으로 실행.

```
# crontab -e
0 9 * * * /Users/kim-yeonghyeon/workplace/job_crowling/cron.sh >> logs/cron.log 2>&1
```

`cron.sh`는 venv 활성화 후 `python3 -m cli.main`을 실행한다.

---

## 2. 아키텍처

Clean Architecture (Ports & Adapters). 의존성은 **바깥 → 안쪽** 방향으로만 흐른다.

```
cli/          — 진입점 + Composition Root (어댑터 조립)
  ↓
adapters/     — 외부 시스템 어댑터 (포트 구현체)
  ↓
usecase/      — 시나리오 (포트 Protocol만 의존)
  ↓
domain/       — 순수 비즈니스 규칙 (외부 의존 0개)
```

**핵심 규칙:** `domain/`, `usecase/` 안에서는 `requests`, `bs4`, `discord`, 파일 I/O 등을 import하지 않는다. 그런 코드는 `adapters/`에만 둔다.

---

## 3. 프로젝트 구조

```
job_crowling/
├── cli/
│   ├── main.py             # 메인 진입점 — 어댑터 조립 + RecommendJobs 실행
│   ├── resume_gap.py       # 이력서 갭 분석 진입점
│   └── bot.py              # Discord 이벤트 봇 진입점 (실시간 리액션)
│
├── domain/
│   ├── job.py              # Job 모델 (pydantic)
│   ├── filter.py           # 4년+ 차단, 경력 범위 등 순수 필터 함수
│   └── ranking.py          # keyword_score() — 키워드 기반 점수 계산
│
├── usecase/
│   ├── ports.py            # 5개 포트 Protocol 정의
│   └── recommend_today.py  # RecommendJobs 유스케이스
│
├── adapters/
│   ├── crawlers/
│   │   ├── composite.py    # CompositeCrawler — job_bot.collect_all 래핑
│   │   ├── wanted.py       # 원티드 어댑터
│   │   ├── saramin.py      # 사람인 어댑터
│   │   ├── jobkorea.py     # 잡코리아 어댑터
│   │   └── filters.py      # 크롤러 공통 필터 유틸
│   ├── repository/
│   │   └── json_pool.py    # JsonJobRepository — job_pool.* 래핑
│   ├── snapshot/
│   │   └── markdown_store.py # MarkdownSnapshotStore — 공고 원문 저장
│   ├── ranker/
│   │   ├── keyword.py      # KeywordRanker — domain 함수만 사용
│   │   └── agent_with_fallback.py # AgentWithFallbackRanker — claude CLI + fallback
│   └── notifier/
│       └── discord_webhook.py # DiscordWebhookNotifier — 웹훅 발송 + 기록
│
├── core/
│   ├── config.py           # AppConfig (pydantic) + load_config()
│   └── path.py             # 경로 상수
│
├── data/
│   ├── jobs_pool.json      # 전체 공고 풀 (first_seen/last_seen/status)
│   ├── closed_jobs.json    # 마감 확정 공고 아카이브
│   ├── jobs_history.json   # Discord 발송 기록 (날짜 → 메시지 ID)
│   ├── applied.json        # 리액션 상태 (applied/interested/rejected)
│   └── snapshots/{date}/   # 공고 원문 Markdown
│
├── resume/
│   ├── 이력서.txt          # agent_rank.py가 Claude에게 직접 읽히는 파일
│   └── 경력기술서.txt
│
├── config.json             # 키워드/경력/사이트/Discord 설정
├── config.example.json     # 설정 템플릿
│
# 레거시 모듈 (어댑터가 지연 import로 호출)
├── job_bot.py              # 크롤러 + 공고 수집 로직
├── job_pool.py             # 풀 관리 — 신규/열림/닫힘 추적
├── agent_rank.py           # claude -p CLI 호출로 이력서 기반 랭킹
├── snapshot.py             # URL fetch → Markdown 저장
├── reaction_sync.py        # Discord API 폴링으로 리액션 동기화
└── status.py               # 구직 현황 요약
```

---

## 4. 데이터 흐름

```
cron 트리거 (09:00)
  ↓
cli/main.py — 어댑터 조립 (Composition Root)
  ↓
reaction_sync.sync_once()   ← 리액션 동기화 (applied.json 갱신)
  ↓
RecommendJobs.execute(mode)
  1. snapshot_store.cleanup(retain_days=30)
  2. crawler.fetch()         → CompositeCrawler → job_bot.collect_all
  3. repo.load/update/       → JsonJobRepository → job_pool.*
     flush_closed/save
  4. repo.candidates(mode)   → 후보 공고 선정
  5. ranker.rank(top_n)      → AgentWithFallbackRanker
     └─ claude -p (이력서 기반) → 실패 시 KeywordRanker fallback
  6. snapshot_store.fetch_batch(top) → Markdown 저장
  7. notifier.notify_recommendations() → Discord 웹훅 발송
```

### 실행 모드

| 모드 | 설명 |
|------|------|
| `today` | 오늘 신규 공고만 추천 (기본) |
| `cumulative` | 지금까지 열린 공고 전체 중 추천 |
| `review` | 관심 공고(`interested` 리액션) 리뷰 |

---

## 5. 포트 (usecase/ports.py)

| 포트 | 메서드 | 구현체 |
|------|--------|--------|
| `JobCrawler` | `fetch() → list[dict]` | `CompositeCrawler` |
| `JobRepository` | `load/save/update/flush_closed/candidates/summary` | `JsonJobRepository` |
| `SnapshotStore` | `cleanup/fetch_batch` | `MarkdownSnapshotStore` |
| `Ranker` | `rank(jobs, top_n) → (top, rest)` | `AgentWithFallbackRanker`, `KeywordRanker` |
| `Notifier` | `notify_recommendations(top, rest, snapshots, label)` | `DiscordWebhookNotifier` |

---

## 6. 사이트별 수집 전략

### 원티드
- 엔드포인트: `/api/chaos/navigation/v1/results` (공개 JSON API)
- 경력/지역 필터링은 클라이언트에서 수행

### 사람인 / 잡코리아
- HTML 파싱 (BeautifulSoup)
- 셀렉터 변경 시 `adapters/crawlers/{saramin,jobkorea}.py`만 수정

### 공통
- User-Agent는 실제 브라우저처럼 설정
- 키워드 사이 `time.sleep(1)` 적용 (차단 회피)
- 타임아웃 15초, collector별 독립 try/except (한 사이트 실패 시 전체 중단 없음)

---

## 7. AI 랭킹 (agent_rank.py)

`claude -p` CLI를 subprocess로 호출. `resume/이력서.txt`와 `resume/경력기술서.txt`를 Read 툴로 읽게 한 뒤 JSON 형식으로 Top N 공고를 반환받는다.

- 타임아웃: 5분
- Claude CLI 없거나 타임아웃 시 → `KeywordRanker` (keyword_score 기반)로 자동 fallback
- `AgentWithFallbackRanker`가 분기 책임을 담당

---

## 8. 상태 파일

| 파일 | 내용 |
|------|------|
| `data/jobs_pool.json` | 전체 공고 풀. first_seen / last_seen / status / miss_count |
| `data/closed_jobs.json` | 2회 연속 누락 시 이동하는 마감 아카이브 |
| `data/jobs_history.json` | Discord 발송 기록 (날짜 → 메시지 ID 포함) |
| `data/applied.json` | 리액션 상태 (`applied` / `interested` / `rejected`) |
| `data/snapshots/{date}/` | 공고 URL 원문 Markdown (30일 보관) |

---

## 9. 설정 (config.json)

```json
{
  "keywords": ["백엔드", "서버"],
  "exclude_keywords": ["시니어", "리드"],
  "years_min": 1,
  "years_max": 3,
  "include_newbie": false,
  "locations": ["서울", "경기", "인천"],
  "sites": { "wanted": true, "saramin": true, "jobkorea": true },
  "max_per_site": 0,
  "discord": {
    "webhook_url": "...",
    "bot_token": "...",
    "channel_id": "...",
    "top_n": 10
  }
}
```

---

## 10. Discord 연동

| 기능 | 방식 |
|------|------|
| 공고 발송 | 웹훅 (`discord.webhook_url`) — Top N 개별 메시지 |
| 리액션 동기화 | `reaction_sync.py` (폴링, 1회성) 또는 `cli/bot.py` (실시간 이벤트) |
| 이력서 갭 분석 | `cli/resume_gap.py --send` 로 Discord 발송 |

---

## 11. 테스트

`tests/test_recommend_today.py` — fake 어댑터 5개를 주입, monkeypatch 0개.

```bash
source venv/bin/activate && python -m pytest -q
```

새 use case 추가 시 같은 패턴으로 fake adapter를 만들어 테스트한다.

---

## 12. 확장 패턴

### 새 알림 채널 (예: Slack)
1. `adapters/notifier/slack.py`에 `SlackNotifier` 작성 (`notify_recommendations` 구현)
2. `cli/main.py`에서 `DiscordWebhookNotifier` → `SlackNotifier` 교체
3. domain/usecase 0줄 변경

### 새 크롤러 (예: 점핏)
1. `adapters/crawlers/jumpit.py`에 `JumpitCrawler` 작성 (`fetch() → list[dict]`)
2. `CompositeCrawler`에 합치거나 use case에 두 번째 crawler로 주입
3. `config.json`의 `sites.*`에 토글 추가

### 새 랭킹 전략
- 순수 점수 규칙 → `domain/ranking.py`
- 외부 호출 포함 → `adapters/ranker/`에 새 클래스

### 새 use case (예: 주간 리포트)
1. `usecase/weekly_report.py`에 클래스 작성 — 필요한 포트만 생성자로 주입
2. `cli/weekly.py`에 진입점 추가

---

*자세한 설치/실행 명령은 CLAUDE.md, 장기 로드맵은 docs/ROADMAP.md 참고.*
