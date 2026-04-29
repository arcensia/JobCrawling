#!/usr/bin/env python3
"""로컬 에이전트 — Ollama로 의도 파악 후 프로젝트 CLI 실행."""

import json
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma3:4b"
VENV_PYTHON = str(Path(__file__).parent / "venv" / "bin" / "python3")
BASE_DIR = str(Path(__file__).parent)

COMMANDS = {
    "recommend":        [VENV_PYTHON, "-m", "cli.main", "--ranker", "ollama"],
    "recommend_claude": [VENV_PYTHON, "-m", "cli.main"],
    "recommend_norank": [VENV_PYTHON, "-m", "cli.main", "--no-rank"],
    "status":           [VENV_PYTHON, "status.py"],
    "gap":              [VENV_PYTHON, "-m", "cli.resume_gap"],
    "gap_send":         [VENV_PYTHON, "-m", "cli.resume_gap", "--send"],
}

INTENT_SYSTEM = """\
너는 채용 봇 인텐트 분류기야. 사용자 입력을 보고 아래 중 하나를 JSON으로만 답해. 다른 텍스트 없이 JSON만.

{"action": "recommend"}        → 공고 수집/추천/발송 (Ollama 랭킹)
{"action": "recommend_claude"} → 공고 수집/추천/발송 (Claude 랭킹 명시 시)
{"action": "recommend_norank"} → 랭킹 없이 수집/발송
{"action": "status"}           → 지원 현황/상태 조회
{"action": "gap"}              → 이력서 갭 분석 (발송 없음)
{"action": "gap_send"}         → 이력서 갭 분석 + Discord 발송
{"action": "none"}             → 위 중 해당 없음
"""

SUMMARY_SYSTEM = """\
채용 봇 실행 결과를 한국어로 3줄 이내로 요약해줘. 핵심 수치(수집 건수, Top N, 발송 여부)를 포함해.
오류가 있으면 원인을 짧게 설명해줘.
"""


def _ollama(system: str, user: str, temperature: float = 0.1) -> str:
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream": False,
        "options": {"temperature": temperature},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["message"]["content"].strip()


def detect_intent(user_input: str) -> str:
    raw = _ollama(INTENT_SYSTEM, user_input)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return "none"
    data = json.loads(raw[start:end])
    return data.get("action", "none")


def run_command(action: str) -> str:
    cmd = COMMANDS.get(action)
    if not cmd:
        return ""
    print(f"[agent] 실행: {' '.join(cmd[1:])}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
    output = result.stdout + result.stderr
    return output


def summarize(output: str) -> str:
    if not output.strip():
        return "실행 결과가 없습니다."
    return _ollama(SUMMARY_SYSTEM, output, temperature=0.3)


def handle(user_input: str) -> None:
    print(f"[agent] 입력: {user_input}")

    try:
        action = detect_intent(user_input)
    except urllib.error.URLError:
        print("[agent] Ollama 연결 실패 — ollama serve 실행 중인지 확인하세요.")
        return

    print(f"[agent] 의도: {action}")

    if action == "none":
        print("[agent] 알 수 없는 요청입니다. 다음 중 하나로 말씀해주세요:")
        print("  - 공고 수집/추천/발송")
        print("  - 지원 현황")
        print("  - 이력서 갭 분석")
        return

    output = run_command(action)
    print("\n--- 실행 로그 ---")
    print(output)
    print("--- 요약 ---")
    print(summarize(output))


def main() -> None:
    if len(sys.argv) > 1:
        handle(" ".join(sys.argv[1:]))
        return

    print(f"로컬 채용 봇 (모델: {MODEL}) — 종료: Ctrl+C")
    print("예) 공고 수집해줘 / 지원 현황 보여줘 / 이력서 갭 분석해줘\n")
    while True:
        try:
            user_input = input("❯ ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n종료")
            break
        if not user_input:
            continue
        handle(user_input)
        print()


if __name__ == "__main__":
    main()
