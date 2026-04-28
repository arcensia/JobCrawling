"""job_pool.py 테스트 — 풀 관리 핵심 로직"""

import json
import pytest
from job_pool import (
    update_pool, set_reaction, get_candidates,
    flush_closed, pool_summary,
    load_pool, save_pool, load_closed,
)


# ── update_pool ───────────────────────────────────────────────────

class TestUpdatePool:
    def test_신규_공고_추가(self, sample_jobs):
        pool = update_pool({}, sample_jobs, "2026-04-20")

        assert len(pool) == len(sample_jobs)
        for entry in pool.values():
            assert entry["first_seen"] == "2026-04-20"
            assert entry["last_seen"]  == "2026-04-20"
            assert entry["status"]     == "open"
            assert entry["reaction"]   is None
            assert entry["miss_count"] == 0

    def test_기존_공고_last_seen_갱신(self, sample_jobs):
        pool = update_pool({}, sample_jobs, "2026-04-20")
        pool = update_pool(pool, sample_jobs, "2026-04-21")

        for entry in pool.values():
            assert entry["first_seen"] == "2026-04-20"   # 변경 없음
            assert entry["last_seen"]  == "2026-04-21"   # 갱신
            assert entry["miss_count"] == 0

    def test_누락_공고_miss_count_증가(self, sample_jobs):
        pool = update_pool({}, sample_jobs, "2026-04-20")
        # 다음날 크롤링에서 0번 공고 제외
        pool = update_pool(pool, sample_jobs[1:], "2026-04-21")

        from domain.job import make_job_id
        missing_id = make_job_id(sample_jobs[0])
        assert pool[missing_id]["miss_count"] == 1
        assert pool[missing_id]["status"]     == "open"

    def test_2회_누락시_closed_처리(self, sample_jobs):
        pool = update_pool({}, sample_jobs, "2026-04-20")
        pool = update_pool(pool, sample_jobs[1:], "2026-04-21")
        pool = update_pool(pool, sample_jobs[1:], "2026-04-22")

        from domain.job import make_job_id
        missing_id = make_job_id(sample_jobs[0])
        assert pool[missing_id]["status"]    == "closed"
        assert pool[missing_id]["closed_at"] == "2026-04-22"

    def test_closed_공고는_open_복원_안됨(self, sample_jobs):
        pool = update_pool({}, sample_jobs, "2026-04-20")
        pool = update_pool(pool, sample_jobs[1:], "2026-04-21")
        pool = update_pool(pool, sample_jobs[1:], "2026-04-22")  # closed 처리
        pool = update_pool(pool, sample_jobs,     "2026-04-23")  # 다시 등장

        from domain.job import make_job_id
        jid = make_job_id(sample_jobs[0])
        assert pool[jid]["status"] == "closed"   # 복원되지 않음

    def test_중복_공고_없음(self, sample_jobs):
        pool = update_pool({}, sample_jobs, "2026-04-20")
        pool = update_pool(pool, sample_jobs, "2026-04-20")  # 같은 날 재실행

        assert len(pool) == len(sample_jobs)


# ── set_reaction ─────────────────────────────────────────────────

class TestSetReaction:
    def test_reaction_설정(self, base_pool):
        jid = list(base_pool.keys())[0]
        changed = set_reaction(base_pool, jid, "applied", "2026-04-21")

        assert changed is True
        assert base_pool[jid]["reaction"]    == "applied"
        assert base_pool[jid]["reaction_at"] == "2026-04-21"

    def test_reaction_null_복원(self, base_pool):
        jid = list(base_pool.keys())[0]
        set_reaction(base_pool, jid, "applied",  "2026-04-21")
        changed = set_reaction(base_pool, jid, None, "2026-04-22")

        assert changed is True
        assert base_pool[jid]["reaction"]    is None
        assert base_pool[jid]["reaction_at"] is None

    def test_동일_reaction_변경_없음(self, base_pool):
        jid = list(base_pool.keys())[0]
        set_reaction(base_pool, jid, "interested", "2026-04-21")
        changed = set_reaction(base_pool, jid, "interested", "2026-04-22")

        assert changed is False

    def test_존재하지_않는_job_id(self, base_pool):
        changed = set_reaction(base_pool, "nonexistent", "applied", "2026-04-21")
        assert changed is False


# ── get_candidates ───────────────────────────────────────────────

class TestGetCandidates:
    def test_today_모드_오늘_신규만(self, sample_jobs):
        pool = update_pool({}, sample_jobs[:3], "2026-04-20")
        pool = update_pool(pool, sample_jobs,   "2026-04-21")  # 나머지 추가

        candidates = get_candidates(pool, "today", "2026-04-21")
        titles = {j["title"] for j in candidates}

        # 2026-04-21 에 신규 추가된 공고만 포함
        assert sample_jobs[3]["title"] in titles
        assert sample_jobs[4]["title"] in titles
        # 2026-04-20 에 이미 있던 공고는 제외
        assert sample_jobs[0]["title"] not in titles

    def test_cumulative_모드_열린_공고_전체(self, sample_jobs):
        pool = update_pool({}, sample_jobs, "2026-04-20")

        candidates = get_candidates(pool, "cumulative", "2026-04-21", max_days=30)
        assert len(candidates) == len(sample_jobs)

    def test_reaction_있는_공고_제외(self, base_pool):
        jid = list(base_pool.keys())[0]
        set_reaction(base_pool, jid, "applied", "2026-04-20")

        candidates = get_candidates(base_pool, "cumulative", "2026-04-20", max_days=30)
        jids = {c["url"] for c in candidates}  # url로 구분
        reacted_url = base_pool[jid]["job"]["url"]
        assert reacted_url not in jids

    def test_closed_공고_제외(self, sample_jobs):
        pool = update_pool({}, sample_jobs, "2026-04-20")
        pool = update_pool(pool, sample_jobs[1:], "2026-04-21")
        pool = update_pool(pool, sample_jobs[1:], "2026-04-22")  # 0번 closed

        candidates = get_candidates(pool, "cumulative", "2026-04-22", max_days=30)
        titles = {j["title"] for j in candidates}
        assert sample_jobs[0]["title"] not in titles

    def test_cutoff_날짜_초과_제외(self, sample_jobs):
        pool = update_pool({}, sample_jobs, "2026-04-01")  # 40일 전

        candidates = get_candidates(pool, "cumulative", "2026-05-10", max_days=30)
        assert len(candidates) == 0


# ── flush_closed ──────────────────────────────────────────────────

class TestFlushClosed:
    def test_closed_항목_이동(self, sample_jobs, tmp_path, monkeypatch):
        import job_pool
        monkeypatch.setattr(job_pool, "CLOSED_PATH", tmp_path / "closed_jobs.json")

        pool = update_pool({}, sample_jobs, "2026-04-20")
        pool = update_pool(pool, sample_jobs[1:], "2026-04-21")
        pool = update_pool(pool, sample_jobs[1:], "2026-04-22")  # 0번 closed

        before_count = len(pool)
        pool = flush_closed(pool)

        assert len(pool) == before_count - 1
        closed = json.loads((tmp_path / "closed_jobs.json").read_text())
        assert len(closed) == 1

    def test_open_항목은_유지(self, sample_jobs, tmp_path, monkeypatch):
        import job_pool
        monkeypatch.setattr(job_pool, "CLOSED_PATH", tmp_path / "closed_jobs.json")

        pool = update_pool({}, sample_jobs, "2026-04-20")
        pool = flush_closed(pool)  # closed 없음

        assert len(pool) == len(sample_jobs)


# ── pool_summary ──────────────────────────────────────────────────

class TestPoolSummary:
    def test_기본_집계(self, base_pool):
        summary = pool_summary(base_pool)

        assert summary["open"]   == len(base_pool)
        assert summary["closed"] == 0
        assert summary["applied"] == 0

    def test_reaction_포함_집계(self, base_pool):
        ids = list(base_pool.keys())
        set_reaction(base_pool, ids[0], "applied",    "2026-04-21")
        set_reaction(base_pool, ids[1], "interested", "2026-04-21")
        set_reaction(base_pool, ids[2], "rejected",   "2026-04-21")

        summary = pool_summary(base_pool)
        assert summary["applied"]    == 1
        assert summary["interested"] == 1
        assert summary["rejected"]   == 1
        assert summary["open"]       == len(base_pool)   # status 는 여전히 open


# ── save_pool / load_pool 왕복 ────────────────────────────────────

class TestPersistence:
    def test_save_load_왕복(self, base_pool, tmp_path, monkeypatch):
        import job_pool
        monkeypatch.setattr(job_pool, "POOL_PATH", tmp_path / "jobs_pool.json")

        save_pool(base_pool)
        loaded = load_pool()

        assert loaded.keys() == base_pool.keys()
        for jid in base_pool:
            assert loaded[jid]["status"] == base_pool[jid]["status"]
