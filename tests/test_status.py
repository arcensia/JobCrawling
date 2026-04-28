"""status.py 테스트 — 집계 로직 + 출력 포맷"""

import json
from datetime import datetime, timedelta

import pytest


# ── _group_applied ────────────────────────────────────────────────

class TestGroupApplied:
    def test_status별_분류(self, sample_applied):
        from status import _group_applied

        groups = _group_applied(sample_applied)

        assert len(groups["applied"])    == 1
        assert len(groups["interested"]) == 1
        assert len(groups["rejected"])   == 1

    def test_최신순_정렬(self):
        from status import _group_applied

        applied = [
            {"job_id": "a", "status": "applied", "reacted_at": "2026-04-20"},
            {"job_id": "b", "status": "applied", "reacted_at": "2026-04-22"},
            {"job_id": "c", "status": "applied", "reacted_at": "2026-04-21"},
        ]
        groups = _group_applied(applied)
        dates = [a["reacted_at"] for a in groups["applied"]]
        assert dates == sorted(dates, reverse=True)

    def test_빈_리스트(self):
        from status import _group_applied

        groups = _group_applied([])
        assert groups["applied"]    == []
        assert groups["interested"] == []
        assert groups["rejected"]   == []


# ── _this_week_counts ─────────────────────────────────────────────

class TestThisWeekCounts:
    def test_이번주_건수_집계(self):
        from status import _this_week_counts

        today  = datetime.now().strftime("%Y-%m-%d")
        old    = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

        applied = [
            {"status": "applied",    "reacted_at": today},
            {"status": "applied",    "reacted_at": today},
            {"status": "interested", "reacted_at": today},
            {"status": "rejected",   "reacted_at": old},   # 7일 초과 → 제외
        ]

        counts = _this_week_counts(applied)
        assert counts["applied"]    == 2
        assert counts["interested"] == 1
        assert counts["rejected"]   == 0

    def test_빈_리스트(self):
        from status import _this_week_counts

        counts = _this_week_counts([])
        assert counts == {"applied": 0, "interested": 0, "rejected": 0}

    def test_경계_날짜_포함(self):
        from status import _this_week_counts

        boundary = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        applied = [{"status": "applied", "reacted_at": boundary}]

        counts = _this_week_counts(applied)
        assert counts["applied"] == 1


# ── _unreviewed_count ────────────────────────────────────────────

class TestUnreviewedCount:
    def test_reaction_없는_open만_카운트(self, base_pool):
        from status import _unreviewed_count
        from adapters.repository.json_pool import set_reaction

        total_open = len(base_pool)
        jid = list(base_pool.keys())[0]
        set_reaction(base_pool, jid, "applied", "2026-04-21")

        assert _unreviewed_count(base_pool) == total_open - 1

    def test_closed_제외(self, base_pool):
        from status import _unreviewed_count

        # status를 직접 closed 로 설정
        jid = list(base_pool.keys())[0]
        base_pool[jid]["status"] = "closed"

        assert _unreviewed_count(base_pool) == len(base_pool) - 1

    def test_전부_리뷰됨(self, base_pool):
        from status import _unreviewed_count
        from adapters.repository.json_pool import set_reaction

        for jid in base_pool:
            set_reaction(base_pool, jid, "rejected", "2026-04-21")

        assert _unreviewed_count(base_pool) == 0


# ── build_summary ─────────────────────────────────────────────────

class TestBuildSummary:
    def _patch_paths(self, mocker, tmp_path, applied, pool):
        import status as s_mod

        applied_path = tmp_path / "applied.json"
        pool_path    = tmp_path / "jobs_pool.json"
        applied_path.write_text(json.dumps(applied, ensure_ascii=False), encoding="utf-8")
        pool_path.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")

        mocker.patch.object(s_mod, "APPLIED_PATH", applied_path)
        mocker.patch.object(s_mod, "POOL_PATH",    pool_path)

    def test_출력에_섹션_포함(self, sample_applied, base_pool, mocker, tmp_path):
        from status import build_summary

        self._patch_paths(mocker, tmp_path, sample_applied, base_pool)
        output = build_summary()

        assert "✅ 지원" in output
        assert "🎯 관심" in output
        assert "❌ 패스" in output
        assert "이번 주" in output
        assert "미검토 공고" in output

    def test_지원_건수_정확(self, sample_applied, base_pool, mocker, tmp_path):
        from status import build_summary

        self._patch_paths(mocker, tmp_path, sample_applied, base_pool)
        output = build_summary()

        assert "✅ 지원 (1건)" in output
        assert "🎯 관심 (1건)" in output

    def test_detail_모드_더보기_없음(self, mocker, tmp_path):
        from status import build_summary

        # 6건 applied (기본 5건만 보여주고 "...외" 표시)
        many_applied = [
            {
                "job_id": f"id{i}", "company": f"회사{i}", "title": f"공고{i}",
                "url": "", "site": "원티드", "status": "applied",
                "reacted_at": "2026-04-20", "snapshot_path": None,
            }
            for i in range(6)
        ]
        self._patch_paths(mocker, tmp_path, many_applied, {})

        normal  = build_summary(detail=False)
        detailed = build_summary(detail=True)

        assert "외" in normal          # "...외 1건"
        assert "외" not in detailed    # 전체 표시 시 없음
