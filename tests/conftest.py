"""
공통 pytest fixture

- tmp_data_dir : 테스트마다 격리된 임시 data 디렉토리
- sample_jobs  : fixtures/sample_jobs.json 로드
- sample_history / sample_applied : fixtures/*.json 로드
- pool_with_jobs : update_pool 적용된 기본 pool
"""

import json
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROJECT_ROOT = Path(__file__).parent.parent

# job_pool, reaction_sync 등 프로젝트 모듈 import 가능하게
sys.path.insert(0, str(PROJECT_ROOT))


# ── 기본 데이터 fixture ────────────────────────────────────────────

@pytest.fixture
def sample_jobs() -> list:
    return json.loads((FIXTURES_DIR / "sample_jobs.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_history() -> dict:
    return json.loads((FIXTURES_DIR / "sample_history.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_applied() -> list:
    return json.loads((FIXTURES_DIR / "sample_applied.json").read_text(encoding="utf-8"))


# ── 임시 파일 경로 fixture (테스트 격리) ──────────────────────────

@pytest.fixture
def tmp_pool_path(tmp_path) -> Path:
    return tmp_path / "jobs_pool.json"


@pytest.fixture
def tmp_closed_path(tmp_path) -> Path:
    return tmp_path / "closed_jobs.json"


@pytest.fixture
def tmp_applied_path(tmp_path) -> Path:
    return tmp_path / "applied.json"


@pytest.fixture
def tmp_history_path(tmp_path, sample_history) -> Path:
    p = tmp_path / "jobs_history.json"
    p.write_text(json.dumps(sample_history, ensure_ascii=False), encoding="utf-8")
    return p


# ── 기본 pool fixture ─────────────────────────────────────────────

@pytest.fixture
def base_pool(sample_jobs) -> dict:
    """sample_jobs 를 2026-04-20 에 first_seen 된 pool 로 구성."""
    from job_pool import update_pool
    pool = {}
    return update_pool(pool, sample_jobs, "2026-04-20")
