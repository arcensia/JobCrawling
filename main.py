#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
채용공고 봇 메인 진입점

흐름:
  1. 크롤링 (job_bot.py)
  2. jobs_pool 갱신 — 신규/열림/닫힘 관리 (job_pool.py)
  3. 모드에 따라 후보 공고 선정
       today      : 오늘 처음 올라온 공고
       cumulative : 현재 열린 공고 전체 (최근 30일)
  4. Claude 에이전트 랭킹 (agent_rank.py) → fallback: 키워드 점수
  5. Top N 스냅샷 저장 (snapshot.py)
  6. Discord 발송 (discord_notifier.py)

실행 예시:
  python3 main.py                      # 오늘 신규 공고 (default)
  python3 main.py --mode cumulative    # 전체 열린 공고 중 추천
  python3 main.py --no-rank            # 에이전트 없이 키워드 정렬
"""

import argparse
import datetime
import traceback
from pathlib import Path

from job_bot import load_config, collect_all, to_xlsx, to_html, REPORTS_DIR
from snapshot import fetch_snapshots_batch
from discord_notifier import send_header, send_top_jobs, send_rest_jobs, save_records
from agent_rank import agent_rank
from job_pool import (
    load_pool, save_pool,
    update_pool, sync_applied, flush_closed,
    get_candidates, pool_summary,
)

BASE_DIR = Path(__file__).parent


def load_applied() -> list:
    path = BASE_DIR / "data" / "applied.json"
    if path.exists():
        import json
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def rank_jobs_simple(jobs: list, top_n: int) -> tuple[list, list]:
    """에이전트 실패 시 키워드 점수 fallback 정렬"""
    PRIORITY_KEYWORDS = [
        "fastapi", "python", "kafka", "mongodb", "비동기",
        "백엔드", "docker", "k8s", "kubernetes",
        "java", "kotlin", "spring", "node.js", "go", "golang",
        "redis", "postgresql", "mysql", "aws", "gcp",
    ]

    def exp_score(job: dict) -> int:
        exp   = job.get("experience", "")
        loc   = job.get("location", "")
        title = job.get("title", "")
        full  = f"{exp} {loc} {title}".lower()

        if "신입" in full:
            return 20
        if "경력3년" in full or "3년↑" in full:
            return 10
        if any(f"{y}년↑" in full or f"경력{y}년" in full for y in ["1", "2"]):
            return 30
        try:
            parts = exp.replace("년", "").split("~")
            ann_from = int(parts[0])
            ann_to   = int(parts[1]) if len(parts) > 1 else 99
            if 1 <= ann_from <= 3 and ann_to <= 3:
                return 30
            if ann_from == 0:
                return 20
            if ann_from >= 3:
                return 10
        except (ValueError, IndexError):
            pass
        return 30

    def score(job: dict) -> tuple:
        text = job.get("title", "").lower()
        kw   = sum(1 for kw in PRIORITY_KEYWORDS if kw in text)
        return (exp_score(job), kw)

    ranked = sorted(jobs, key=score, reverse=True)
    return ranked[:top_n], ranked[top_n:]


def main(mode: str = "today", no_rank: bool = False):
    cfg = load_config()
    dc  = cfg.get("discord", {})
    webhook_url = dc.get("webhook_url", "")
    top_n = int(dc.get("top_n", 10))
    today = datetime.date.today().isoformat()

    print(f"=== 채용공고 수집 시작 ({today}) [mode={mode}] ===")

    # 1. 리액션 자동 동기화 (봇 꺼져 있어도 놓치지 않음)
    try:
        from reaction_sync import sync_once
        sync_once()
    except Exception as e:
        print(f"[sync] 자동 동기화 실패 (계속 진행): {e}")

    # 2. 크롤링
    all_jobs = collect_all(cfg)
    print(f"[crawl] {len(all_jobs)}건 수집")

    # 2. pool 갱신
    pool = load_pool()
    pool = update_pool(pool, all_jobs, today)

    applied = load_applied()
    pool = sync_applied(pool, applied)
    pool = flush_closed(pool)

    summary = pool_summary(pool)
    print(f"[pool] open={summary['open']} / applied={summary['applied']} / 전체={len(pool)}")
    save_pool(pool)

    # 3. 리포트 저장 (전체 open 공고 기준)
    open_jobs = [e["job"] for e in pool.values() if e["status"] == "open"]
    xlsx_path = REPORTS_DIR / f"jobs_{today}.xlsx"
    to_xlsx(open_jobs, xlsx_path)
    html = to_html(open_jobs, today)
    (REPORTS_DIR / f"jobs_{today}.html").write_text(html, encoding="utf-8")
    print(f"[report] 저장 완료: {xlsx_path.name}")

    # 4. 모드별 후보 선정
    candidates = get_candidates(pool, mode=mode, today=today)
    if not candidates:
        print(f"[rank] 후보 없음 (mode={mode}) — 발송 생략")
        return
    print(f"[candidates] {len(candidates)}건 ({mode} 모드)")

    # 5. 랭킹
    applied_companies = list({a["company"] for a in applied if a.get("status") == "applied"})
    if not no_rank:
        agent_result = agent_rank(candidates, top_n, mode=mode, applied_companies=applied_companies)
        if agent_result:
            top_jobs, rest_jobs = agent_result
            print(f"[rank] 에이전트 Top {len(top_jobs)} / 나머지 {len(rest_jobs)}")
        else:
            top_jobs, rest_jobs = rank_jobs_simple(candidates, top_n)
            print(f"[rank] fallback Top {len(top_jobs)} / 나머지 {len(rest_jobs)}")
    else:
        top_jobs, rest_jobs = rank_jobs_simple(candidates, top_n)
        print(f"[rank] --no-rank Top {len(top_jobs)} / 나머지 {len(rest_jobs)}")

    # 6. Top N 스냅샷

    print(f"[snapshot] Top {len(top_jobs)}건 원문 저장 중...")
    job_snapshots = fetch_snapshots_batch(top_jobs, today=today, delay=1.2)

    # 7. Discord 발송
    if not webhook_url:
        print("[discord] webhook_url 미설정 — 발송 생략")
        return

    mode_label = "오늘 신규" if mode == "today" else "누적 전체"
    try:
        send_header(
            webhook_url,
            total=len(candidates),
            top_n=len(top_jobs),
            today=today,
            mode_label=mode_label,
        )
        records = send_top_jobs(webhook_url, top_jobs, job_snapshots, today=today)
        send_rest_jobs(webhook_url, rest_jobs, today=today)
        save_records(records, today=today)
        print(f"[discord] 발송 완료 — Top {len(top_jobs)}건 개별 + 나머지 {len(rest_jobs)}건 묶음")
    except Exception as e:
        print(f"[discord] 발송 실패: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["today", "cumulative"],
        default="today",
        help="today: 오늘 신규 공고 / cumulative: 열린 공고 전체",
    )
    parser.add_argument("--no-rank", action="store_true", help="키워드 점수로만 정렬 (에이전트 없이)")
    args = parser.parse_args()
    main(mode=args.mode, no_rank=args.no_rank)
