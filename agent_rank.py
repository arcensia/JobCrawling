#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code (claude -p) 를 이용한 이력서 기반 공고 랭킹

흐름:
  1. 공고 리스트(JSON) + 이력서 파일 경로를 프롬프트에 담아 claude -p 호출
  2. Claude가 Read 툴로 이력서를 직접 읽고 평가
  3. JSON 스키마로 Top N 반환
  4. 실패 시 None 반환 → main.py 에서 fallback
"""

import json
import subprocess

from core.path import PROJECT_ROOT as BASE_DIR, RESUME_DIR

_MODE_CONTEXT = {
    "today": (
        "이 공고들은 오늘 새로 올라온 공고야. "
        "신규인 만큼 빠르게 지원할 가치가 있는 것을 우선순위로 뽑아줘."
    ),
    "cumulative": (
        "이 공고들은 현재 열려있는 공고 전체야. "
        "지금 시점에서 지원자에게 가장 적합한 것을 골라줘. "
        "오래 열려있는 공고라도 좋은 포지션이면 적극 추천해."
    ),
}

PROMPT_TEMPLATE = """\
너는 백엔드 개발자 취업 멘토야. 지원자의 이력서를 읽고 아래 공고 리스트에서 \
가장 적합한 Top {top_n}개를 골라줘.

이력서 파일을 Read 툴로 읽어서 참고해:
- {resume_path}
- {career_path}

[모드 안내]
{mode_context}

{applied_block}\
---
공고 리스트 (JSON):
{jobs_json}
---

평가 기준:
1. 기술 스택 일치도 (지원자 주력: Python/FastAPI/Kafka/MongoDB/Spring)
2. 경력 연차: 1~3년 > 신입 가능 > "3년 이상" 허용 (지원자 총 경력 약 2년 5개월)
3. 반드시 top에서 제외하고 red_flags에 기록:
   - "경력 4년 이상" 또는 그 이상이 필수인 공고 (3년 이상은 허용)
   - 시니어·리드·팀장급 전용
   - 포괄임금·도메인 완전 불일치
4. 지원자 경험(B2B SaaS, AI/ML 플랫폼, 데이터 파이프라인)과 겹치면 가산점

반드시 아래 JSON 형식으로만 응답해. 다른 텍스트 없이 JSON 블록만:
{{
  "top": [
    {{
      "job_id": "공고 ID 문자열",
      "rank": 1,
      "reason": "추천 이유 1~2줄 (한국어)",
      "fit_points": ["강점1", "강점2"],
      "red_flags": []
    }}
  ]
}}
"""


def agent_rank(
    jobs: list,
    top_n: int = 10,
    mode: str = "today",
    applied_companies: list | None = None,
) -> tuple[list, list] | None:
    """
    Claude Code CLI로 이력서 기반 공고 랭킹.
    반환: (top_jobs, rest_jobs) 또는 None(실패 시 fallback 사용)
    top_jobs 각 항목에 _reason, _fit_points, _red_flags 필드 추가됨.
    """
    from snapshot import job_id as make_job_id

    resume_path = RESUME_DIR / "이력서.txt"
    career_path = RESUME_DIR / "경력기술서.txt"

    if not resume_path.exists():
        print("[agent] 이력서 없음 → fallback")
        return None

    # job_id 붙인 공고 리스트 (불필요한 필드 제거해 토큰 절약)
    id_to_job = {}
    slim_jobs = []
    for j in jobs:
        jid = make_job_id(j)
        id_to_job[jid] = j
        slim_jobs.append({
            "job_id": jid,
            "site": j.get("site", ""),
            "company": j.get("company", ""),
            "title": j.get("title", ""),
            "experience": j.get("experience", ""),
            "location": j.get("location", ""),
            "tags": j.get("tags", ""),
        })

    jobs_json = json.dumps(slim_jobs, ensure_ascii=False, indent=2)

    if applied_companies:
        names = "\n".join(f"  - {c}" for c in applied_companies)
        applied_block = (
            f"[지원 이력]\n"
            f"아래 회사에는 이미 지원했어. 동일 회사 공고가 있으면 "
            f"red_flags 에 '같은 회사에 이미 지원함' 을 추가해줘:\n"
            f"{names}\n\n"
        )
    else:
        applied_block = ""

    prompt = PROMPT_TEMPLATE.format(
        top_n=top_n,
        resume_path=resume_path,
        career_path=career_path,
        mode_context=_MODE_CONTEXT.get(mode, _MODE_CONTEXT["today"]),
        applied_block=applied_block,
        jobs_json=jobs_json,
    )

    print(f"[agent] Claude 호출 중 ({len(jobs)}건 평가)...")
    try:
        result = subprocess.run(
            [
                "claude", "-p",
                "--output-format", "json",
                "--allowed-tools", "Read",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(BASE_DIR),
        )

        if result.returncode != 0:
            print(f"[agent] 오류 (exit {result.returncode}): {result.stderr[:300]}")
            return None

        outer = json.loads(result.stdout)
        raw_text = outer.get("result", "")

        # 응답에서 JSON 블록 추출
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"[agent] JSON 없음 → fallback\n응답: {raw_text[:200]}")
            return None

        data = json.loads(raw_text[start:end])
        top_items = data.get("top", [])
        if not top_items:
            print("[agent] top 리스트 비어있음 → fallback")
            return None

        # agent 순서대로 top_jobs 구성, 메타 필드 첨부
        top_ids = {item["job_id"] for item in top_items}
        top_jobs = []
        for item in top_items[:top_n]:
            jid = item["job_id"]
            if jid not in id_to_job:
                continue
            j = dict(id_to_job[jid])
            j["_reason"] = item.get("reason", "")
            j["_fit_points"] = item.get("fit_points", [])
            j["_red_flags"] = item.get("red_flags", [])
            top_jobs.append(j)

        rest_jobs = [j for j in jobs if make_job_id(j) not in top_ids]

        print(f"[agent] 완료 — Top {len(top_jobs)}건 선정")
        return top_jobs, rest_jobs

    except subprocess.TimeoutExpired:
        print("[agent] 타임아웃 (5분) → fallback")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[agent] 파싱 오류: {e} → fallback")
        return None
    except FileNotFoundError:
        print("[agent] claude CLI 없음 → fallback")
        return None
