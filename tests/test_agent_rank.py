"""agent_rank.py 테스트 — 프롬프트 빌드 + JSON 파싱 (subprocess 모킹)"""

import json
import pytest


def _make_claude_output(top_items: list) -> str:
    """agent_rank 가 기대하는 claude -p JSON 출력 포맷 생성."""
    inner = json.dumps({"top": top_items}, ensure_ascii=False)
    return json.dumps({"result": inner})


def _slim(jobs: list) -> list:
    """agent_rank 내부에서 만드는 slim_jobs 형태 (job_id 필드 추가)."""
    from snapshot import job_id as make_job_id
    return [
        {
            "job_id": make_job_id(j),
            "site": j.get("site", ""),
            "company": j.get("company", ""),
            "title": j.get("title", ""),
        }
        for j in jobs
    ]


# ── 프롬프트 빌드 ─────────────────────────────────────────────────

class TestPromptBuilding:
    def test_applied_companies_프롬프트_포함(self, sample_jobs, mocker, tmp_path):
        """applied_companies 가 프롬프트에 주입되는지 확인."""
        from snapshot import job_id as make_job_id

        slim = _slim(sample_jobs[:1])
        captured = {}

        def fake_run(cmd, input=None, **kwargs):
            captured["prompt"] = input
            result = mocker.MagicMock()
            result.returncode = 0
            result.stdout = _make_claude_output([
                {
                    "job_id": slim[0]["job_id"],
                    "rank": 1,
                    "reason": "좋음",
                    "fit_points": [],
                    "red_flags": [],
                }
            ])
            return result

        mocker.patch("agent_rank.subprocess.run", side_effect=fake_run)

        # 이력서 파일 임시 생성
        resume_dir = tmp_path / "resume"
        resume_dir.mkdir()
        (resume_dir / "이력서.txt").write_text("이력서 내용", encoding="utf-8")

        import agent_rank
        mocker.patch.object(agent_rank, "RESUME_DIR", resume_dir)

        agent_rank.agent_rank(
            sample_jobs[:1],
            top_n=1,
            applied_companies=["테스트컴퍼니", "샘플소프트"],
        )

        assert "테스트컴퍼니" in captured["prompt"]
        assert "샘플소프트" in captured["prompt"]

    def test_applied_companies_없으면_블록_미포함(self, sample_jobs, mocker, tmp_path):
        slim = _slim(sample_jobs[:1])
        captured = {}

        def fake_run(cmd, input=None, **kwargs):
            captured["prompt"] = input
            result = mocker.MagicMock()
            result.returncode = 0
            result.stdout = _make_claude_output([
                {"job_id": slim[0]["job_id"], "rank": 1, "reason": "", "fit_points": [], "red_flags": []}
            ])
            return result

        mocker.patch("agent_rank.subprocess.run", side_effect=fake_run)

        resume_dir = tmp_path / "resume"
        resume_dir.mkdir()
        (resume_dir / "이력서.txt").write_text("이력서", encoding="utf-8")

        import agent_rank
        mocker.patch.object(agent_rank, "RESUME_DIR", resume_dir)

        agent_rank.agent_rank(sample_jobs[:1], top_n=1, applied_companies=[])

        assert "[지원 이력]" not in captured["prompt"]


# ── JSON 파싱 ─────────────────────────────────────────────────────

class TestJsonParsing:
    def _run_with_output(self, mocker, tmp_path, jobs, stdout: str, top_n: int = 2):
        result = mocker.MagicMock()
        result.returncode = 0
        result.stdout = stdout
        mocker.patch("agent_rank.subprocess.run", return_value=result)

        resume_dir = tmp_path / "resume"
        resume_dir.mkdir(exist_ok=True)
        (resume_dir / "이력서.txt").write_text("이력서", encoding="utf-8")

        import agent_rank
        mocker.patch.object(agent_rank, "RESUME_DIR", resume_dir)

        return agent_rank.agent_rank(jobs, top_n=top_n)

    def test_정상_응답_파싱(self, sample_jobs, mocker, tmp_path):
        # 전체 5건 넘기고 상위 2건만 top 으로 반환
        slim = _slim(sample_jobs)
        stdout = _make_claude_output([
            {"job_id": slim[0]["job_id"], "rank": 1, "reason": "추천", "fit_points": ["Python"], "red_flags": []},
            {"job_id": slim[1]["job_id"], "rank": 2, "reason": "좋음", "fit_points": [],          "red_flags": []},
        ])

        top, rest = self._run_with_output(mocker, tmp_path, sample_jobs, stdout, top_n=2)
        assert len(top)  == 2
        assert len(rest) == len(sample_jobs) - 2   # 5 - 2 = 3
        assert top[0]["_reason"] == "추천"
        assert top[0]["_fit_points"] == ["Python"]

    def test_앞뒤_텍스트_있어도_JSON_추출(self, sample_jobs, mocker, tmp_path):
        slim = _slim(sample_jobs[:1])
        inner = json.dumps({"top": [
            {"job_id": slim[0]["job_id"], "rank": 1, "reason": "ok", "fit_points": [], "red_flags": []}
        ]}, ensure_ascii=False)
        # 앞뒤에 설명 텍스트가 있는 경우
        raw_with_text = f"물론이죠! 다음은 결과입니다:\n{inner}\n분석 완료!"
        stdout = json.dumps({"result": raw_with_text})

        result = self._run_with_output(mocker, tmp_path, sample_jobs, stdout)
        assert result is not None
        top, _ = result
        assert len(top) == 1

    def test_빈_top_리스트_None_반환(self, sample_jobs, mocker, tmp_path):
        stdout = json.dumps({"result": json.dumps({"top": []})})
        result = self._run_with_output(mocker, tmp_path, sample_jobs, stdout)
        assert result is None

    def test_잘못된_JSON_None_반환(self, sample_jobs, mocker, tmp_path):
        stdout = json.dumps({"result": "이건 JSON이 아니에요"})
        result = self._run_with_output(mocker, tmp_path, sample_jobs, stdout)
        assert result is None

    def test_subprocess_실패_None_반환(self, sample_jobs, mocker, tmp_path):
        result = mocker.MagicMock()
        result.returncode = 1
        result.stderr = "error"
        mocker.patch("agent_rank.subprocess.run", return_value=result)

        resume_dir = tmp_path / "resume"
        resume_dir.mkdir(exist_ok=True)
        (resume_dir / "이력서.txt").write_text("이력서", encoding="utf-8")

        import agent_rank
        mocker.patch.object(agent_rank, "RESUME_DIR", resume_dir)

        assert agent_rank.agent_rank(sample_jobs[:1]) is None

    def test_claude_CLI_없으면_None_반환(self, sample_jobs, mocker, tmp_path):
        mocker.patch("agent_rank.subprocess.run", side_effect=FileNotFoundError)

        resume_dir = tmp_path / "resume"
        resume_dir.mkdir(exist_ok=True)
        (resume_dir / "이력서.txt").write_text("이력서", encoding="utf-8")

        import agent_rank
        mocker.patch.object(agent_rank, "RESUME_DIR", resume_dir)

        assert agent_rank.agent_rank(sample_jobs[:1]) is None

    def test_이력서_없으면_None_반환(self, sample_jobs, mocker, tmp_path):
        import agent_rank
        mocker.patch.object(agent_rank, "RESUME_DIR", tmp_path / "no_resume")

        assert agent_rank.agent_rank(sample_jobs[:1]) is None
