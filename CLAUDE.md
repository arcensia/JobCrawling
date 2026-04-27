# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

채용공고 자동 수집 봇 — 원티드/사람인/잡코리아에서 백엔드/풀스택 주니어(1~3년차) 공고를 매일 수집하여 이력서 기반으로 AI 랭킹 후 Discord로 발송합니다.

Clean Architecture (Ports & Adapters) 패턴으로 리팩토링되어 있습니다 — 자세한 구조는 [Architecture](#architecture) 참고.

장기 비전·로드맵·검토 중인 확장 아이디어는 [docs/ROADMAP.md](docs/ROADMAP.md) 참고.

## Setup

```bash
# venv 권장
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# bot.py(Discord 봇)는 별도 패키지 필요
pip install discord.py
```

`config.json`에 Discord webhook/bot 설정이 필요합니다. `config.example.json` 참고.

## Common Commands

```bash
# 오늘 신규 공고 추천 (default, 매일 수동/cron용)
python3 -m cli.main
python3 -m cli.main --mode today

# 지금까지 열린 공고 전체 중 추천
python3 -m cli.main --mode cumulative

# Claude 랭킹 없이 키워드 점수만으로 실행
python3 -m cli.main --no-rank

# 이력서 갭 분석 (지난 7일 스냅샷 기준)
python3 -m cli.resume_gap
python3 -m cli.resume_gap --send       # Discord 발송 포함
python3 -m cli.resume_gap --days 14    # 기간 조정

# Discord 리액션 동기화 (applied.json 갱신)
python3 reaction_sync.py               # 폴링 방식 (1회성)
python3 -m cli.bot                     # 이벤트 방식 (실시간 상주)

# 테스트 실행
source venv/bin/activate && python -m pytest -q
python -m pytest tests/test_recommend_today.py -v

# 환경 및 패키지 확인
./test.sh

# cron 자동 실행 등록 (매일 09:00)
# crontab -e → 아래 줄 추가:
# 0 9 * * * /Users/kim-yeonghyeon/workplace/job_crowling/cron.sh >> logs/cron.log 2>&1
```

## Architecture

Clean Architecture (Ports & Adapters). 의존성은 항상 **바깥 → 안쪽**으로만 흐릅니다.

```
cli/             — 진입점 + Composition Root (의존성 조립)
  ↓ depends on
adapters/        — 외부 시스템 어댑터 (포트 구현체)
  ↓ depends on
usecase/         — 시나리오 (포트만 의존, 외부 라이브러리 모름)
  ↓ depends on
domain/          — 순수 비즈니스 규칙 (외부 의존 0개)
```

**핵심 규칙:** `domain/`, `usecase/` 안에서는 `requests`, `bs4`, `discord`, 파일 I/O 등 외부 의존을 **절대 import하지 않습니다**. 그런 코드는 `adapters/`에 둡니다.

### 데이터 흐름 (today 모드)

```
cli/main.py (Composition Root)
  ├─ 어댑터 인스턴스 생성 (CompositeCrawler, JsonJobRepository, ...)
  └─ RecommendJobs(...).execute(mode)
       ↓
       usecase/recommend_today.py
        1. snapshot_store.cleanup(retain_days=30)
        2. crawler.fetch()                    → adapters/crawlers/composite.py → job_bot.collect_all
        3. repo.load/update/flush_closed/save → adapters/repository/json_pool.py → job_pool.*
        4. repo.candidates(mode)              → 후보 선정
        5. ranker.rank(candidates, top_n)     → adapters/ranker/* (agent + fallback)
        6. snapshot_store.fetch_batch(top)    → adapters/snapshot/markdown_store.py → snapshot.*
        7. notifier.notify_recommendations()  → adapters/notifier/discord_webhook.py
```

### 디렉터리 구조

| 경로 | 역할 |
|------|------|
| `domain/job.py` | `Job` 모델 (pydantic) |
| `domain/filter.py` | 4년+ 차단, 경력 범위 등 순수 필터 함수 |
| `domain/ranking.py` | 키워드 점수 기반 랭킹 (`keyword_score`) |
| `usecase/ports.py` | 5개 포트 (`JobCrawler`, `JobRepository`, `SnapshotStore`, `Ranker`, `Notifier`) — Protocol 정의 |
| `usecase/recommend_today.py` | `RecommendJobs` 유스케이스 — 포트만 의존, 외부 import 0개 |
| `adapters/crawlers/composite.py` | `CompositeCrawler` — `job_bot.collect_all` 래핑 |
| `adapters/repository/json_pool.py` | `JsonJobRepository` — `job_pool.*` 래핑 |
| `adapters/snapshot/markdown_store.py` | `MarkdownSnapshotStore` — `snapshot.*` 래핑 |
| `adapters/ranker/keyword.py` | `KeywordRanker` — 도메인 함수만 사용 |
| `adapters/ranker/agent_with_fallback.py` | `AgentWithFallbackRanker` — `agent_rank` + keyword fallback (Strategy + Composite) |
| `adapters/notifier/discord_webhook.py` | `DiscordWebhookNotifier` — Discord 웹훅 발송 + 기록 |
| `cli/main.py` | 메인 CLI 진입점 — 어댑터 조립 + use case 실행 |
| `cli/resume_gap.py` | 이력서 갭 분석 진입점 |
| `cli/bot.py` | Discord 이벤트 봇 진입점 |

### 레거시 모듈 (어댑터가 래핑하는 대상)

리팩토링 중 점진 이주를 위해 다음 모듈은 그대로 유지되며, 어댑터에서 *지연 import*로 호출합니다:

| 파일 | 역할 |
|------|------|
| `job_bot.py` | 원티드(JSON API), 사람인/잡코리아(HTML 파싱) 크롤러 + 리포트 |
| `job_pool.py` | 풀 관리 — 신규/열림/닫힘 추적, 후보 필터링, 요약 |
| `agent_rank.py` | `claude -p` CLI 호출로 이력서 기반 Top N 랭킹 |
| `snapshot.py` | 공고 URL 원문 fetch → Markdown 저장 |
| `reaction_sync.py` | Discord API 폴링으로 리액션 동기화 |
| `core/config.py`, `core/path.py` | 설정 로딩 + 경로 상수 |

새 기능을 추가할 땐 가능한 한 `adapters/`에 새 어댑터를 작성하고, 위 레거시 파일은 건드리지 않는 방향을 권장합니다.

### 상태 파일

- `data/jobs_pool.json` — 모든 공고 풀 (first_seen/last_seen/status, miss_count)
- `data/closed_jobs.json` — 마감 확정 공고 아카이브 (2회 연속 누락 시 이동)
- `data/jobs_history.json` — Discord 발송 기록 (날짜 → 메시지 ID 포함)
- `data/applied.json` — 리액션 상태 (`applied`/`interested`/`rejected`)
- `data/snapshots/{date}/` — 공고 원문 Markdown
- `reports/` — Excel/HTML 리포트

### 설정 (`config.json`)

- `keywords` / `exclude_keywords` — 크롤링 필터
- `years_min` / `years_max` — 경력 범위 (기본 1~3년)
- `sites.wanted/saramin/jobkorea` — 사이트별 활성화 여부
- `discord.webhook_url` — 웹훅 발송 URL (필수)
- `discord.bot_token` / `channel_id` — bot.py, reaction_sync.py에 필요
- `discord.top_n` — 개별 발송할 Top N 수 (기본 10)

### agent_rank.py 동작 방식

`claude -p` CLI를 subprocess로 호출하여 `resume/이력서.txt`와 `resume/경력기술서.txt`를 Read 툴로 읽게 한 뒤 JSON 형식으로 Top N 공고를 반환받습니다. Claude CLI가 없거나 타임아웃(5분)이 나면 `domain/ranking.py`의 `keyword_score()`로 fallback합니다 (`AgentWithFallbackRanker`가 분기 책임).

### 크롤러 특이사항

- 원티드: `/api/chaos/navigation/v1/results` JSON API 사용, 클라이언트에서 경력/지역 필터링
- 사람인/잡코리아: HTML 파싱 (BeautifulSoup), 각 사이트 구조 변경 시 `job_bot.py`의 해당 셀렉터만 수정
- 각 collector는 독립 try/except — 한 사이트 실패가 전체 실행에 영향 없음
- 키워드 사이 `time.sleep(1)` 적용 (차단 회피)

## Extension Patterns

리팩토링된 구조 덕분에 다음 작업은 **use case와 domain을 건드리지 않고** 가능합니다:

### 새 알림 채널 추가 (예: Slack)
1. `adapters/notifier/slack.py`에 `SlackNotifier` 클래스 작성 — `Notifier` Protocol의 `notify_recommendations` 구현
2. `cli/main.py`에서 `DiscordWebhookNotifier(...)` 줄을 `SlackNotifier(...)`로 교체
3. 끝. domain/usecase 0줄 변경.

### 새 크롤러 추가 (예: 점핏)
1. `adapters/crawlers/jumpit.py`에 `JumpitCrawler` 작성 (`fetch() -> list[dict]`)
2. `CompositeCrawler`에 합치거나 use case에 두 번째 crawler로 주입
3. 사이트 토글은 `config.json`의 `sites.*`에 추가

### 새 랭킹 전략 추가
1. `adapters/ranker/`에 새 클래스 작성 (`rank(jobs, top_n) -> (top, rest)`)
2. `cli/main.py`의 분기에 추가 (`--ranker xxx` 플래그 등)
3. **순수 점수 규칙은 `domain/ranking.py`에**, **외부 호출이 들어가면 `adapters/ranker/`에**

### 새 use case 추가 (예: 주간 리포트)
1. `usecase/weekly_report.py`에 클래스 작성 — 필요한 포트만 생성자로 받음
2. 새 포트가 필요하면 `usecase/ports.py`에 추가
3. `cli/`에 새 진입점 (`cli/weekly.py`) 추가

## Testing

`tests/test_recommend_today.py`가 use case 단위 테스트의 모범 — fake 객체 5개를 주입하고 monkeypatch는 0개입니다. 새 use case를 추가하면 같은 패턴으로 fake adapter를 만들어 테스트하세요.

```bash
source venv/bin/activate && python -m pytest -q
```

## Resume Files

`resume/이력서.txt`, `resume/경력기술서.txt` — agent_rank.py가 Claude에게 직접 읽히는 파일입니다. 지원자 정보(Python/FastAPI/Kafka/MongoDB/Spring 주력, 경력 약 2년 5개월)가 담겨 있습니다.
