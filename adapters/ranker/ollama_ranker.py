"""Ollama 로컬 LLM 랭커 + 실패 시 키워드 점수 fallback."""

import json
import urllib.request
import urllib.error

from core.path import RESUME_DIR
from domain.job import make_job_id
from domain.ranking import keyword_score

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
    "review": (
        "이 공고들은 지원자가 이미 관심 표시한 공고들이야. "
        "지금 바로 지원할 만한 순서대로 골라줘. "
        "지원하기 어려운 이유가 있으면 red_flags에 구체적으로 적어줘."
    ),
}

PROMPT_TEMPLATE = """\
너는 백엔드 개발자 취업 멘토야. 지원자의 이력서를 읽고 아래 공고 리스트에서 \
가장 적합한 Top {top_n}개를 골라줘.

[이력서]
{resume_text}

[경력기술서]
{career_text}

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

반드시 아래 JSON 형식으로만 응답해. 다른 텍스트 없이 JSON만:
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

DEFAULT_MODEL = "gemma3:4b"
OLLAMA_URL = "http://localhost:11434/api/chat"


def _read_resume() -> tuple[str, str]:
    resume_path = RESUME_DIR / "이력서.txt"
    career_path = RESUME_DIR / "경력기술서.txt"
    resume_text = resume_path.read_text(encoding="utf-8") if resume_path.exists() else ""
    career_text = career_path.read_text(encoding="utf-8") if career_path.exists() else ""
    return resume_text, career_text


def _call_ollama(prompt: str, model: str, timeout: int) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())["message"]["content"]


def ollama_rank(
    jobs: list,
    top_n: int = 10,
    mode: str = "today",
    applied_companies: list | None = None,
    model: str = DEFAULT_MODEL,
    timeout: int = 300,
) -> tuple[list, list] | None:
    resume_text, career_text = _read_resume()
    if not resume_text:
        print("[ollama] 이력서 없음 → fallback")
        return None

    id_to_job = {}
    slim_jobs = []
    for j in jobs:
        jid = make_job_id(j)
        id_to_job[jid] = j
        slim_jobs.append({
            "job_id":     jid,
            "site":       j.get("site", ""),
            "company":    j.get("company", ""),
            "title":      j.get("title", ""),
            "experience": j.get("experience", ""),
            "location":   j.get("location", ""),
            "tags":       j.get("tags", ""),
        })

    applied_block = ""
    if applied_companies:
        names = "\n".join(f"  - {c}" for c in applied_companies)
        applied_block = (
            f"[지원 이력]\n아래 회사에는 이미 지원했어. 동일 회사 공고가 있으면 "
            f"red_flags에 '같은 회사에 이미 지원함'을 추가해줘:\n{names}\n\n"
        )

    prompt = PROMPT_TEMPLATE.format(
        top_n=top_n,
        resume_text=resume_text,
        career_text=career_text,
        mode_context=_MODE_CONTEXT.get(mode, _MODE_CONTEXT["today"]),
        applied_block=applied_block,
        jobs_json=json.dumps(slim_jobs, ensure_ascii=False, indent=2),
    )

    print(f"[ollama] {model} 호출 중 ({len(jobs)}건 평가)...")
    try:
        raw = _call_ollama(prompt, model, timeout)

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"[ollama] JSON 없음 → fallback\n응답: {raw[:200]}")
            return None

        data = json.loads(raw[start:end])
        top_items = data.get("top", [])
        if not top_items:
            print("[ollama] top 리스트 비어있음 → fallback")
            return None

        top_ids = {item["job_id"] for item in top_items}
        top_jobs = []
        for item in top_items[:top_n]:
            jid = item["job_id"]
            if jid not in id_to_job:
                continue
            j = dict(id_to_job[jid])
            j["_reason"]     = item.get("reason", "")
            j["_fit_points"] = item.get("fit_points", [])
            j["_red_flags"]  = item.get("red_flags", [])
            top_jobs.append(j)

        rest_jobs = [j for j in jobs if make_job_id(j) not in top_ids]
        print(f"[ollama] 완료 — Top {len(top_jobs)}건 선정")
        return top_jobs, rest_jobs

    except urllib.error.URLError:
        print("[ollama] 연결 실패 (Ollama 실행 중인지 확인) → fallback")
        return None
    except TimeoutError:
        print("[ollama] 타임아웃 → fallback")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[ollama] 파싱 오류: {e} → fallback")
        return None


class OllamaRanker:
    def __init__(
        self,
        mode: str,
        applied_companies: list[str],
        model: str = DEFAULT_MODEL,
        timeout: int = 300,
    ):
        self._mode = mode
        self._applied = applied_companies
        self._model = model
        self._timeout = timeout

    def rank(self, jobs: list[dict], top_n: int) -> tuple[list[dict], list[dict]]:
        result = ollama_rank(
            jobs, top_n,
            mode=self._mode,
            applied_companies=self._applied,
            model=self._model,
            timeout=self._timeout,
        )
        if result:
            return result
        return keyword_score(jobs, top_n)
