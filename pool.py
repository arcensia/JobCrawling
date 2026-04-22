#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공고 풀 관리 — jobs_pool.json / closed_jobs.json

jobs_pool.json : 현재 열려있거나 추적 중인 공고
closed_jobs.json : 마감 확정 공고 (별도 보관)

마감 판단: MISS_THRESHOLD 회 연속 크롤링에서 사라지면 closed로 이동
"""

import json
from datetime import date, timedelta
from pathlib import Path

from snapshot import job_id as make_job_id

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
POOL_PATH = DATA_DIR / "jobs_pool.json"
CLOSED_PATH = DATA_DIR / "closed_jobs.json"

MISS_THRESHOLD = 2  # 연속 누락 N회면 마감 처리


def _load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_pool(crawled_jobs: list, applied_ids: set, today: str) -> tuple[dict, list]:
    """
    오늘 크롤링 결과로 pool 업데이트.

    반환: (pool, newly_closed)
    - pool: 갱신된 jobs_pool (open/applied 상태 공고)
    - newly_closed: 이번 실행에서 새로 마감 처리된 공고 목록
    """
    pool = _load(POOL_PATH)
    closed = _load(CLOSED_PATH)

    crawled_map = {make_job_id(j): j for j in crawled_jobs}
    crawled_ids = set(crawled_map.keys())

    to_close = []  # pool에서 삭제할 job_id

    for jid, entry in pool.items():
        if jid in applied_ids:
            entry["status"] = "applied"
        elif jid in crawled_ids:
            entry["last_seen"] = today
            entry["miss_count"] = 0
            entry["job"] = crawled_map[jid]  # 최신 데이터로 갱신
        else:
            if entry["status"] == "open":
                entry["miss_count"] = entry.get("miss_count", 0) + 1
                if entry["miss_count"] >= MISS_THRESHOLD:
                    entry["status"] = "closed"
                    entry["closed_at"] = today
                    to_close.append(jid)

    newly_closed = []
    for jid in to_close:
        entry = pool.pop(jid)
        closed[jid] = entry
        newly_closed.append(entry)

    # 오늘 새로 크롤링된 공고 추가
    for jid, job in crawled_map.items():
        if jid not in pool and jid not in closed:
            pool[jid] = {
                "first_seen": today,
                "last_seen": today,
                "status": "applied" if jid in applied_ids else "open",
                "miss_count": 0,
                "job": job,
            }

    _save(POOL_PATH, pool)
    _save(CLOSED_PATH, closed)

    open_cnt = sum(1 for e in pool.values() if e["status"] == "open")
    print(f"[pool] open {open_cnt}건 / 신규마감 {len(newly_closed)}건 / 누적마감 {len(closed)}건")
    return pool, newly_closed


def get_candidates(pool: dict, mode: str, today: str, lookback_days: int = 30) -> list:
    """
    mode='today'      : first_seen == 오늘 AND status == open
    mode='cumulative' : status == open AND last_seen >= today - lookback_days
    """
    cutoff = (date.fromisoformat(today) - timedelta(days=lookback_days)).isoformat()
    result = []
    for entry in pool.values():
        if entry["status"] != "open":
            continue
        if mode == "today" and entry["first_seen"] != today:
            continue
        if mode == "cumulative" and entry["last_seen"] < cutoff:
            continue
        result.append(entry["job"])
    return result
