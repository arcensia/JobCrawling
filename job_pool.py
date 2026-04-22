#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공고 풀(pool) 관리

jobs_pool.json  : 지금까지 본 모든 공고 (open / closed / applied)
closed_jobs.json: 마감 확정된 공고 아카이브

Pool entry 구조:
{
  "<job_id>": {
    "first_seen":  "2026-04-22",
    "last_seen":   "2026-04-22",
    "status":      "open",       # open | closed | applied
    "miss_count":  0,            # 크롤링 누락 연속 횟수 (2회 이상 → closed)
    "job":         { ...공고 원본 필드... }
  }
}
"""

import json
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR  = BASE_DIR / "data"
POOL_PATH   = DATA_DIR / "jobs_pool.json"
CLOSED_PATH = DATA_DIR / "closed_jobs.json"

MISS_THRESHOLD = 2   # 연속 누락 N회 이상이면 closed 처리


def load_pool() -> dict:
    if POOL_PATH.exists():
        return json.loads(POOL_PATH.read_text(encoding="utf-8"))
    return {}


def save_pool(pool: dict):
    DATA_DIR.mkdir(exist_ok=True)
    POOL_PATH.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")


def load_closed() -> dict:
    if CLOSED_PATH.exists():
        return json.loads(CLOSED_PATH.read_text(encoding="utf-8"))
    return {}


def save_closed(closed: dict):
    DATA_DIR.mkdir(exist_ok=True)
    CLOSED_PATH.write_text(json.dumps(closed, ensure_ascii=False, indent=2), encoding="utf-8")


def update_pool(pool: dict, fresh_jobs: list, today: str) -> dict:
    """
    크롤링 결과(fresh_jobs)로 pool 갱신.
    - 신규 공고: first_seen=today 로 추가
    - 기존 공고: last_seen=today, miss_count=0
    - 누락된 open 공고: miss_count++; >= MISS_THRESHOLD 이면 closed
    """
    from snapshot import job_id as make_job_id

    fresh_ids = {make_job_id(j): j for j in fresh_jobs}

    # 기존 open 공고 중 이번 크롤에 없으면 miss_count 증가
    for jid, entry in pool.items():
        if entry["status"] != "open":
            continue
        if jid not in fresh_ids:
            entry["miss_count"] += 1
            if entry["miss_count"] >= MISS_THRESHOLD:
                entry["status"] = "closed"
                entry["closed_at"] = today

    # 신규 / 재등장 공고 반영
    for jid, job in fresh_ids.items():
        if jid in pool:
            entry = pool[jid]
            # 한 번 closed/applied 된 건 열림으로 되돌리지 않음
            if entry["status"] == "open":
                entry["last_seen"]  = today
                entry["miss_count"] = 0
                entry["job"] = job   # 필드 업데이트 (제목 변경 등 대응)
        else:
            pool[jid] = {
                "first_seen":  today,
                "last_seen":   today,
                "status":      "open",
                "miss_count":  0,
                "job":         job,
            }

    return pool


def sync_applied(pool: dict, applied: list) -> dict:
    """applied.json 내역을 pool 에 반영 (status=applied)"""
    applied_ids = {a["job_id"] for a in applied}
    for jid, entry in pool.items():
        if jid in applied_ids and entry["status"] == "open":
            entry["status"] = "applied"
    return pool


def flush_closed(pool: dict) -> dict:
    """closed 항목을 closed_jobs.json 으로 이동하고 pool 에서 제거"""
    closed = load_closed()
    to_remove = []
    for jid, entry in pool.items():
        if entry["status"] == "closed":
            closed[jid] = entry
            to_remove.append(jid)
    for jid in to_remove:
        del pool[jid]
    if to_remove:
        save_closed(closed)
        print(f"[pool] {len(to_remove)}건 마감 처리 → closed_jobs.json")
    return pool


def get_candidates(pool: dict, mode: str, today: str, max_days: int = 30) -> list:
    """
    랭킹 후보 공고 반환.

    mode='today'      : 오늘 처음 등장한 공고만
    mode='cumulative' : 최근 max_days 일 내 열린 공고 전체
    """
    cutoff = (
        datetime.date.fromisoformat(today)
        - datetime.timedelta(days=max_days)
    ).isoformat()

    result = []
    for entry in pool.values():
        if entry["status"] != "open":
            continue
        if mode == "today":
            if entry["first_seen"] == today:
                result.append(entry["job"])
        else:  # cumulative
            if entry["last_seen"] >= cutoff:
                result.append(entry["job"])

    return result


def pool_summary(pool: dict) -> dict:
    counts = {"open": 0, "closed": 0, "applied": 0}
    for entry in pool.values():
        s = entry.get("status", "open")
        counts[s] = counts.get(s, 0) + 1
    return counts
