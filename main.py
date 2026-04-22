#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
채용공고 봇 메인 진입점

흐름:
  1. 크롤링 (job_bot.py)
  2. Claude (이 세션)가 이력서 × 공고 매칭/랭킹 → Top N 선별
  3. Top N 스냅샷 저장 (snapshot.py)
  4. Discord 발송 — Top N 개별 + 나머지 묶음 (discord_notifier.py)
  5. jobs_history.json 기록

Claude 매칭 없이 크롤링+발송만 원할 때:
  python3 main.py --no-rank
"""

import argparse
import datetime
import json
import traceback
from pathlib import Path

from job_bot import load_config, collect_all, to_xlsx, to_html, REPORTS_DIR
from snapshot import fetch_snapshots_batch, job_id as make_job_id
from discord_notifier import send_header, send_top_jobs, send_rest_jobs, save_records

BASE_DIR = Path(__file__).parent
RESUME_DIR = BASE_DIR / "resume"


def load_resume() -> str:
    parts = []
    for fname in ["이력서.txt", "경력기술서.txt"]:
        p = RESUME_DIR / fname
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


def load_applied() -> list:
    path = BASE_DIR / "data" / "applied.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def filter_already_applied(jobs: list, applied: list) -> list:
    applied_ids = {a["job_id"] for a in applied}
    return [j for j in jobs if make_job_id(j) not in applied_ids]


def rank_jobs_simple(jobs: list, top_n: int) -> tuple[list, list]:
    """
    API 키 없이 Claude Code 세션에서 랭킹할 때 쓰는 기본 정렬.
    /daily-jobs 커맨드에서 Claude가 직접 판단할 때는 이 함수를 거치지 않음.
    키워드 매칭 점수로 간단 정렬.
    """
    PRIORITY_KEYWORDS = [
        "fastapi", "python", "kafka", "mongodb", "비동기",
        "백엔드", "docker", "k8s", "kubernetes",
        "java", "kotlin", "spring", "node.js", "go", "golang",
        "redis", "postgresql", "mysql", "aws", "gcp",
    ]

    def exp_score(job: dict) -> int:
        """
        경력 우선순위 점수
        1순위 (30): 1~3년차 명시
        2순위 (20): 신입 / 신입가능
        3순위 (10): 3년차 이상(3~N년)
        기타  ( 0): 판단 불가
        """
        exp = job.get("experience", "")
        loc = job.get("location", "")
        title = job.get("title", "")
        full = f"{exp} {loc} {title}".lower()

        # 텍스트 기반 우선 (사람인 location 필드 패턴)
        if "신입" in full:
            return 20
        if "경력3년" in full or "3년↑" in full:
            return 10
        if any(f"{y}년↑" in full or f"경력{y}년" in full for y in ["1", "2"]):
            return 30

        # 원티드: experience 필드 "annual_from~annual_to년" 형식
        try:
            parts = exp.replace("년", "").split("~")
            ann_from = int(parts[0])
            ann_to = int(parts[1]) if len(parts) > 1 else 99
            if 1 <= ann_from <= 3 and ann_to <= 3:
                return 30
            if ann_from == 0:
                return 20
            if ann_from >= 3:
                return 10
        except (ValueError, IndexError):
            pass

        return 30  # 사람인 exp_cd=1,2,3 결과는 기본 1~3년으로 간주

    def score(job: dict) -> tuple:
        # title만 사용 — tags는 사람인 직종 카테고리 레이블이 섞여 있어 신뢰도 낮음
        text = job.get("title", "").lower()
        kw_score = sum(1 for kw in PRIORITY_KEYWORDS if kw in text)
        return (exp_score(job), kw_score)

    ranked = sorted(jobs, key=score, reverse=True)
    return ranked[:top_n], ranked[top_n:]


def main(no_rank: bool = False):
    cfg = load_config()
    dc = cfg.get("discord", {})
    webhook_url = dc.get("webhook_url", "")
    top_n = int(dc.get("top_n", 10))
    today = datetime.date.today().isoformat()

    print(f"=== 채용공고 수집 시작 ({today}) ===")

    # 1. 크롤링
    all_jobs = collect_all(cfg)
    print(f"[crawl] {len(all_jobs)}건 수집")

    # 2. 이미 지원한 곳 제외
    applied = load_applied()
    jobs = filter_already_applied(all_jobs, applied)
    print(f"[filter] 지원 이력 제외 후 {len(jobs)}건")

    # 3. 리포트 저장 (전체)
    xlsx_path = REPORTS_DIR / f"jobs_{today}.xlsx"
    to_xlsx(jobs, xlsx_path)
    html = to_html(jobs, today)
    (REPORTS_DIR / f"jobs_{today}.html").write_text(html, encoding="utf-8")
    print(f"[report] 저장 완료: {xlsx_path.name}")

    # 4. 랭킹 (--no-rank 이면 단순 정렬)
    top_jobs, rest_jobs = rank_jobs_simple(jobs, top_n)
    print(f"[rank] Top {len(top_jobs)} / 나머지 {len(rest_jobs)}")

    # 5. Top N 스냅샷
    print(f"[snapshot] Top {len(top_jobs)}건 원문 저장 중...")
    job_snapshots = fetch_snapshots_batch(top_jobs, today=today, delay=1.2)

    # 6. Discord 발송
    if not webhook_url:
        print("[discord] webhook_url 미설정 — 발송 생략")
        return

    try:
        send_header(webhook_url, total=len(jobs), top_n=len(top_jobs), today=today)
        records = send_top_jobs(webhook_url, top_jobs, job_snapshots, today=today)
        send_rest_jobs(webhook_url, rest_jobs, today=today)
        save_records(records, today=today)
        print(f"[discord] 발송 완료 — Top {len(top_jobs)}건 개별 + 나머지 {len(rest_jobs)}건 묶음")
    except Exception as e:
        print(f"[discord] 발송 실패: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-rank", action="store_true", help="Claude 랭킹 없이 키워드 점수로만 정렬")
    args = parser.parse_args()
    main(no_rank=args.no_rank)
