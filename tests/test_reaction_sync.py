"""reaction_sync.py 테스트 — Discord 파싱 + 동기화 로직"""

import json
import pytest


# ── _parse_reaction ───────────────────────────────────────────────

class TestParseReaction:
    def _msg(self, emojis: list[tuple[str, int]]) -> dict:
        """테스트용 Discord 메시지 구조 생성."""
        return {
            "reactions": [
                {"emoji": {"name": e}, "count": c}
                for e, c in emojis
            ]
        }

    def test_applied_이모지(self):
        from adapters.sync.reaction import _parse_reaction
        assert _parse_reaction(self._msg([("✅", 1)])) == "applied"

    def test_interested_이모지(self):
        from adapters.sync.reaction import _parse_reaction
        assert _parse_reaction(self._msg([("🎯", 1)])) == "interested"

    def test_rejected_이모지(self):
        from adapters.sync.reaction import _parse_reaction
        assert _parse_reaction(self._msg([("❌", 1)])) == "rejected"

    def test_우선순위_applied_우선(self):
        from adapters.sync.reaction import _parse_reaction
        # ✅ 와 🎯 동시에 — ✅ 가 이겨야 함
        msg = self._msg([("🎯", 1), ("✅", 1)])
        assert _parse_reaction(msg) == "applied"

    def test_우선순위_interested_over_rejected(self):
        from adapters.sync.reaction import _parse_reaction
        msg = self._msg([("❌", 1), ("🎯", 1)])
        assert _parse_reaction(msg) == "interested"

    def test_리액션_없음(self):
        from adapters.sync.reaction import _parse_reaction
        assert _parse_reaction({"reactions": []}) is None
        assert _parse_reaction({}) is None

    def test_count_0_은_무시(self):
        from adapters.sync.reaction import _parse_reaction
        assert _parse_reaction(self._msg([("✅", 0)])) is None

    def test_무관한_이모지_무시(self):
        from adapters.sync.reaction import _parse_reaction
        assert _parse_reaction(self._msg([("😂", 1), ("👍", 1)])) is None


# ── sync_once ────────────────────────────────────────────────────

class TestSyncOnce:
    """requests + job_pool I/O 모킹하여 동기화 로직 검증."""

    def _setup_paths(self, tmp_path, sample_history, sample_applied, monkeypatch):
        """임시 경로를 reaction 어댑터 모듈에 주입."""
        from adapters.sync import reaction as reaction_mod
        import adapters.repository.json_pool as json_pool_mod

        hist_path    = tmp_path / "jobs_history.json"
        applied_path = tmp_path / "applied.json"
        pool_path    = tmp_path / "jobs_pool.json"

        hist_path.write_text(
            json.dumps(sample_history, ensure_ascii=False), encoding="utf-8"
        )
        applied_path.write_text(
            json.dumps(sample_applied, ensure_ascii=False), encoding="utf-8"
        )
        pool_path.write_text(json.dumps({}), encoding="utf-8")

        monkeypatch.setattr(reaction_mod,  "HISTORY_PATH", hist_path)
        monkeypatch.setattr(reaction_mod,  "APPLIED_PATH", applied_path)
        monkeypatch.setattr(json_pool_mod, "POOL_PATH",    pool_path)

        return applied_path, pool_path

    def _mock_config(self, mocker):
        mocker.patch(
            "adapters.sync.reaction._load_config",
            return_value={"discord": {"bot_token": "fake-token", "channel_id": "999"}},
        )

    def _mock_message(self, mocker, reactions_by_msg: dict):
        """message_id → reactions 매핑으로 HTTP GET 모킹."""
        def fake_get(url, **kwargs):
            for msg_id, emojis in reactions_by_msg.items():
                if msg_id in url:
                    resp = mocker.MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {
                        "reactions": [
                            {"emoji": {"name": e}, "count": c}
                            for e, c in emojis
                        ]
                    }
                    resp.raise_for_status = lambda: None
                    return resp
            resp = mocker.MagicMock()
            resp.status_code = 404
            return resp

        mocker.patch("adapters.sync.reaction.requests.get", side_effect=fake_get)

    def test_신규_리액션_applied_json_추가(
        self, tmp_path, sample_history, sample_applied, mocker, monkeypatch
    ):
        from adapters.sync.reaction import sync_once

        applied_path, _ = self._setup_paths(tmp_path, sample_history, [], monkeypatch)
        self._mock_config(mocker)
        self._mock_message(mocker, {"1111111111111111111": [("✅", 1)]})

        mocker.patch("adapters.sync.reaction.time.sleep")
        sync_once()

        result = json.loads(applied_path.read_text(encoding="utf-8"))
        assert any(a["job_id"] == "aaa11111" and a["status"] == "applied" for a in result)

    def test_리액션_상태_변경(
        self, tmp_path, sample_history, sample_applied, mocker, monkeypatch
    ):
        from adapters.sync.reaction import sync_once

        applied_path, _ = self._setup_paths(
            tmp_path, sample_history, sample_applied, monkeypatch
        )
        self._mock_config(mocker)
        self._mock_message(mocker, {"1111111111111111111": [("🎯", 1)]})
        mocker.patch("adapters.sync.reaction.time.sleep")

        sync_once()

        result = json.loads(applied_path.read_text(encoding="utf-8"))
        entry = next(a for a in result if a["job_id"] == "aaa11111")
        assert entry["status"] == "interested"

    def test_리액션_제거시_applied_json_삭제(
        self, tmp_path, sample_history, sample_applied, mocker, monkeypatch
    ):
        from adapters.sync.reaction import sync_once

        applied_path, _ = self._setup_paths(
            tmp_path, sample_history, sample_applied, monkeypatch
        )
        self._mock_config(mocker)
        self._mock_message(mocker, {"1111111111111111111": []})
        mocker.patch("adapters.sync.reaction.time.sleep")

        sync_once()

        result = json.loads(applied_path.read_text(encoding="utf-8"))
        assert not any(a["job_id"] == "aaa11111" for a in result)

    def test_설정_없으면_0_반환(self, mocker):
        from adapters.sync.reaction import sync_once

        mocker.patch(
            "adapters.sync.reaction._load_config",
            return_value={"discord": {}},
        )
        assert sync_once() == 0
