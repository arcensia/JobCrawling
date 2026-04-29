# 레거시 모듈 리팩토링 계획

작성일: 2026-04-28

---

## 전체 의존 관계 (grep 확인 결과)

```
snapshot.job_id ← agent_rank.py:87
snapshot.job_id ← job_pool.py:66
snapshot.job_id ← pool.py:16              ← 원래 계획 누락
snapshot.job_id ← adapters/notifier/discord_webhook.py:82
snapshot.job_id ← tests/test_job_pool.py:40,50,61
snapshot.job_id ← tests/test_agent_rank.py:15,32

job_pool       ← adapters/repository/json_pool.py (lazy import 6개)
job_pool       ← reaction_sync.py:94       ← 치명적 순서 문제
job_pool       ← tests/conftest.py:69
job_pool       ← tests/test_job_pool.py:5,155,170,206
job_pool       ← tests/test_status.py:84,103,116
job_pool       ← tests/test_reaction_sync.py:63

agent_rank     ← adapters/ranker/agent_with_fallback.py:12 (lazy import)
agent_rank     ← tests/test_agent_rank.py:52,59,84,90,105,111,164,170,176,182

reaction_sync  ← cli/main.py:26
reaction_sync  ← tests/test_reaction_sync.py:20~165 (_parse_reaction, sync_once)
```

**핵심 제약**
- `reaction_sync`가 `job_pool`을 직접 import → job_pool 삭제 전에 reaction_sync를 먼저 어댑터로 이주해야 함
- `snapshot.job_id`가 4개 프로덕션 파일 + 2개 테스트 파일에서 참조 → Step 1에서 모두 교체

---

## 리팩토링 순서

### Step 1 — `job_id()` 를 `domain/job.py` 로 이동

**변경 파일**

| 파일 | 작업 |
|------|------|
| `domain/job.py` | `make_job_id(job: dict) -> str` 함수 추가 |
| `snapshot.py` | `from domain.job import make_job_id` 로 교체 (파일은 유지) |
| `job_pool.py` | 동일 교체 |
| `pool.py` | 동일 교체 |
| `agent_rank.py` | 동일 교체 |
| `adapters/notifier/discord_webhook.py` | 동일 교체 |
| `tests/test_job_pool.py` | `from snapshot import job_id` → `from domain.job import make_job_id` |
| `tests/test_agent_rank.py` | 동일 교체 |

**완료 기준**
```bash
grep -rn "from snapshot import job_id" . --include="*.py" | grep -v venv
# → 결과 없음
python -m pytest -q
```

---

### Step 2 — `snapshot.py` 인라인 → `adapters/snapshot/markdown_store.py`

**변경 파일**

| 파일 | 작업 |
|------|------|
| `adapters/snapshot/markdown_store.py` | lazy import 제거, 로직 직접 보유 |

이동할 내용: `HEADERS`, `BODY_SELECTORS`, `_slug()`, `fetch_snapshot()`, `fetch_snapshots_batch()`, `cleanup_old_snapshots()`

테스트 파일 중 snapshot 함수를 직접 import하는 곳 없음 → 테스트 변경 불필요.

**이후 삭제**: `snapshot.py`

**완료 기준**
```bash
grep -rn "from snapshot import\|import snapshot" . --include="*.py" | grep -v venv
# → 결과 없음
python -m pytest -q
```

---

### Step 3 — `reaction_sync.py` → `adapters/sync/reaction.py` (job_pool 삭제 전에 선행)

`reaction_sync.py`가 `job_pool`을 직접 import하므로, job_pool 삭제 전에 먼저 어댑터로 분리한다.

**변경 파일**

| 파일 | 작업 |
|------|------|
| `adapters/sync/__init__.py` | 신규 생성 |
| `adapters/sync/reaction.py` | `ReactionSync` 클래스 신규 생성 |
| `cli/main.py` | `from reaction_sync import sync_once` → `from adapters.sync.reaction import ReactionSync` |
| `reaction_sync.py` | `__main__` 블록만 남긴 얇은 CLI 래퍼로 축소 (10줄 이내) |
| `tests/test_reaction_sync.py` | import 경로를 `adapters.sync.reaction` 로 교체 |

이동할 내용: `REACTION_MAP`, `PRIORITY`, `_load_config()`, `_load_history()`, `_load_applied()`,
`_save_applied()`, `_get_message()`, `_parse_reaction()`, `sync_once()`

`_parse_reaction()`은 `tests/test_reaction_sync.py`에서 직접 import됨 →
어댑터에서 `_parse_reaction`을 모듈 수준 함수로 유지하거나 테스트를 내부 메서드 테스트로 전환.

이 시점에서 `adapters/sync/reaction.py`는 `job_pool`을 lazy import로 유지해도 무방.
(job_pool은 Step 4에서 삭제되므로 Step 4와 함께 교체)

**완료 기준**
```bash
grep -rn "from reaction_sync import sync_once" . --include="*.py" | grep -v venv
# → 결과 없음 (cli/main.py 포함)
python -m pytest -q
```

---

### Step 4 — `job_pool.py` 인라인 → `adapters/repository/json_pool.py`

**변경 파일**

| 파일 | 작업 |
|------|------|
| `adapters/repository/json_pool.py` | lazy import 6개 제거, 로직 직접 보유 |
| `adapters/sync/reaction.py` | `from job_pool import ...` → `adapters/repository/json_pool` 내부 함수 사용 |
| `tests/conftest.py` | `from job_pool import update_pool` → 어댑터 경로로 교체 |
| `tests/test_job_pool.py` | `from job_pool import ...` → 어댑터 경로로 교체 |
| `tests/test_status.py` | `from job_pool import set_reaction` → 어댑터 경로로 교체 |
| `tests/test_reaction_sync.py:63` | `import job_pool` → 어댑터 경로로 교체 |

이동할 내용: `MISS_THRESHOLD`, `_atomic_write()`, `load_pool()`, `save_pool()`,
`load_closed()`, `save_closed()`, `update_pool()`, `flush_closed()`,
`get_candidates()`, `pool_summary()`, `set_reaction()`

`set_reaction()`은 `tests/test_status.py`에서 직접 import되고,
`adapters/sync/reaction.py`에서도 사용하므로 public 함수로 노출 유지.

**이후 삭제**: `job_pool.py`

**완료 기준**
```bash
grep -rn "from job_pool import\|import job_pool" . --include="*.py" | grep -v venv
# → 결과 없음
python -m pytest -q
```

---

### Step 5 — `agent_rank.py` 인라인 → `adapters/ranker/agent_with_fallback.py`

**변경 파일**

| 파일 | 작업 |
|------|------|
| `adapters/ranker/agent_with_fallback.py` | lazy import 제거, 로직 직접 보유 |
| `tests/test_agent_rank.py` | `import agent_rank` → `from adapters.ranker.agent_with_fallback import AgentWithFallbackRanker` (또는 내부 함수) |

이동할 내용: `_MODE_CONTEXT`, `PROMPT_TEMPLATE`, `agent_rank()` 함수 전체

`tests/test_agent_rank.py`는 `agent_rank.subprocess.run` 과 `agent_rank.RESUME_DIR`를 `mocker.patch`로 직접 패칭함 →
어댑터 클래스로 이주 후 패치 대상 경로를 `adapters.ranker.agent_with_fallback.*`으로 교체.

**이후 삭제**: `agent_rank.py`

**완료 기준**
```bash
grep -rn "from agent_rank import\|import agent_rank" . --include="*.py" | grep -v venv
# → 결과 없음
python -m pytest -q
```

---

### Step 6 — `pool.py` / `status.py` / `bot.py` 정리

`pool.py`: 현재 아무 곳에서도 import되지 않음. Step 1에서 `job_id` 교체 후 레거시 의존이 없어지면 삭제 검토.
`status.py`: 레거시 import 없음 (core.path 상수만 사용). 단, `tests/test_status.py`가 `job_pool.set_reaction`을 사용하므로 Step 4 완료 후 테스트가 통과하면 별도 작업 불필요.
`bot.py` (루트): 별도 확인 필요.

---

## 각 단계 완료 체크리스트

- [ ] `grep` 기준 충족 (해당 레거시 모듈 import 0건)
- [ ] `python -m pytest -q` 전체 통과
- [ ] 해당 레거시 파일 삭제 또는 래퍼로 축소

---

## 완료 후 최종 상태

| 파일 | 결과 |
|------|------|
| `snapshot.py` | 삭제 |
| `job_pool.py` | 삭제 |
| `agent_rank.py` | 삭제 |
| `reaction_sync.py` | CLI 래퍼 (~10줄) 로 축소 |
| `pool.py` | 삭제 예정 (Step 6 확인 후) |
| `job_bot.py` | 유지 (크롤러 원본, composite.py가 독립적으로 래핑) |
| `status.py` | 유지 (레거시 의존 없음) |
| `bot.py` | Step 6에서 별도 검토 |
