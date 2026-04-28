"""JSON 파일 기반 풀 저장소 — JobRepository 포트 구현."""

import datetime
import json
import os
import tempfile
from pathlib import Path

from core.path import POOL_PATH, CLOSED_PATH
from domain.job import make_job_id
from domain.filter import is_candidate

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


def get_candidates(
    pool: dict,
    mode: str,
    today: str,
    max_days: int = 30,
    exclude_keywords: list | None = None,
) -> list:
    cutoff = (
        datetime.date.fromisoformat(today) - datetime.timedelta(days=max_days)
    ).isoformat()

    result = []
    for entry in pool.values():
        if entry["status"] != "open":
            continue
        if mode == "review":
            if entry.get("reaction") == "interested":
                result.append(entry["job"])
            continue
        if entry.get("reaction"):
            continue
        if exclude_keywords and not is_candidate(entry["job"], exclude_keywords):
            continue
        if mode == "today":
            if entry["first_seen"] == today:
                result.append(entry["job"])
        else:
            if entry["last_seen"] >= cutoff:
                result.append(entry["job"])

    return result


def pool_summary(pool: dict) -> dict:
    counts = {"open": 0, "closed": 0, "applied": 0, "interested": 0, "rejected": 0}
    for entry in pool.values():
        counts[entry.get("status", "open")] += 1
        r = entry.get("reaction")
        if r:
            counts[r] = counts.get(r, 0) + 1
    return counts


class JsonJobRepository:
    def __init__(self, exclude_keywords: list[str] | None = None):
        self._exclude_keywords = exclude_keywords or []

    def load(self) -> dict:
        return load_pool()

    def save(self, pool: dict) -> None:
        save_pool(pool)

    def update(self, pool: dict, jobs: list[dict], today: str) -> dict:
        return update_pool(pool, jobs, today)

    def flush_closed(self, pool: dict) -> dict:
        return flush_closed(pool)

    def candidates(self, pool: dict, mode: str, today: str) -> list[dict]:
        return get_candidates(pool, mode=mode, today=today, exclude_keywords=self._exclude_keywords)

    def summary(self, pool: dict) -> dict:
        return pool_summary(pool)
