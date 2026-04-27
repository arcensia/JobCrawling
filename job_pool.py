#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공고 풀(pool) 관리

jobs_pool.json  : 지금까지 본 모든 공고
closed_jobs.json: 마감 확정된 공고 아카이브

Pool entry 구조:
{
  "<job_id>": {
    "first_seen":   "2026-04-22",
    "last_seen":    "2026-04-22",
    "status":       "open",       # open | closed  (공고 라이프사이클)
    "reaction":     null,         # null | applied | interested | rejected  (사용자 액션)
    "reaction_at":  null,         # 리액션 날짜
    "miss_count":   0,            # 크롤링 누락 연속 횟수 (2회 이상 → closed)
    "job":          { ...공고 원본 필드... }
  }
}
"""

import json
import os
import tempfile
import datetime

from core.path import POOL_PATH, CLOSED_PATH

MISS_THRESHOLD = 2


def _atomic_write(path: Path, data: str):
    path.parent.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8",
        dir=path.parent, suffix=".tmp", delete=False,
    ) as f:
        f.write(data)
        tmp = f.name
    os.replace(tmp, path)


def load_pool() -> dict:
    if POOL_PATH.exists():
        return json.loads(POOL_PATH.read_text(encoding="utf-8"))
    return {}


def save_pool(pool: dict):
    _atomic_write(POOL_PATH, json.dumps(pool, ensure_ascii=False, indent=2))


def load_closed() -> dict:
    if CLOSED_PATH.exists():
        return json.loads(CLOSED_PATH.read_text(encoding="utf-8"))
    return {}


def save_closed(closed: dict):
    _atomic_write(CLOSED_PATH, json.dumps(closed, ensure_ascii=False, indent=2))


def update_pool(pool: dict, fresh_jobs: list, today: str) -> dict:
    """크롤링 결과로 pool 갱신. 누락 2회 이상 → closed."""
    from snapshot import job_id as make_job_id

    fresh_ids = {make_job_id(j): j for j in fresh_jobs}

    for jid, entry in pool.items():
        if entry["status"] != "open":
            continue
        if jid not in fresh_ids:
            entry["miss_count"] += 1
            if entry["miss_count"] >= MISS_THRESHOLD:
                entry["status"] = "closed"
                entry["closed_at"] = today

    for jid, job in fresh_ids.items():
        if jid in pool:
            entry = pool[jid]
            if entry["status"] == "open":
                entry["last_seen"]  = today
                entry["miss_count"] = 0
                entry["job"]        = job
        else:
            pool[jid] = {
                "first_seen":  today,
                "last_seen":   today,
                "status":      "open",
                "reaction":    None,
                "reaction_at": None,
                "miss_count":  0,
                "job":         job,
            }

    return pool


def set_reaction(pool: dict, job_id: str, reaction: str | None, reaction_at: str) -> bool:
    """pool 내 공고의 reaction 설정. 변경 발생 시 True 반환."""
    if job_id not in pool:
        return False
    entry = pool[job_id]
    old = entry.get("reaction")
    if old == reaction:
        return False
    entry["reaction"]    = reaction
    entry["reaction_at"] = reaction_at if reaction else None
    return True


def flush_closed(pool: dict) -> dict:
    """closed 항목을 closed_jobs.json 으로 이동하고 pool 에서 제거."""
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
    랭킹 후보 반환 — reaction 있는 공고(지원/관심/패스)는 제외.

    mode='today'      : 오늘 처음 등장한 공고만
    mode='cumulative' : 최근 max_days 일 내 열린 공고 전체
    mode='review'     : 관심 표시(interested)한 공고 전체 (지원 결정용)
    """
    cutoff = (
        datetime.date.fromisoformat(today)
        - datetime.timedelta(days=max_days)
    ).isoformat()

    result = []
    for entry in pool.values():
        if entry["status"] != "open":
            continue
        if mode == "review":
            if entry.get("reaction") == "interested":
                result.append(entry["job"])
            continue
        if entry.get("reaction"):       # 이미 반응한 공고 제외
            continue
        if mode == "today":
            if entry["first_seen"] == today:
                result.append(entry["job"])
        else:
            if entry["last_seen"] >= cutoff:
                result.append(entry["job"])

    return result


def pool_summary(pool: dict) -> dict:
    """open/closed + reaction 별 집계."""
    counts = {
        "open": 0, "closed": 0,
        "applied": 0, "interested": 0, "rejected": 0,
    }
    for entry in pool.values():
        counts[entry.get("status", "open")] += 1
        r = entry.get("reaction")
        if r:
            counts[r] = counts.get(r, 0) + 1
    return counts
