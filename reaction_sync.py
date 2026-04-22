#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord 리액션 폴링 → applied.json + jobs_pool.json 동기화

리액션 의미:
  ✅  지원함     → reaction: applied
  🎯  관심있음   → reaction: interested
  ❌  패스       → reaction: rejected
  (없음)         → reaction: null (리액션 제거 시 원복)

사용:
  python3 reaction_sync.py            # 1회 동기화
  python3 reaction_sync.py --dry-run  # 변경 내용만 출력
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR     = Path(__file__).parent
HISTORY_PATH = BASE_DIR / "data" / "jobs_history.json"
APPLIED_PATH = BASE_DIR / "data" / "applied.json"
CONFIG_PATH  = BASE_DIR / "config.json"

REACTION_MAP = {
    "✅": "applied",
    "🎯": "interested",
    "❌": "rejected",
}
PRIORITY = ["✅", "🎯", "❌"]


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def _load_applied() -> list:
    if not APPLIED_PATH.exists():
        return []
    return json.loads(APPLIED_PATH.read_text(encoding="utf-8"))


def _save_applied(data: list):
    APPLIED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_message(token: str, channel_id: str, message_id: str) -> dict | None:
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    headers = {"Authorization": f"Bot {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 404:
        return None
    if r.status_code == 429:
        retry_after = r.json().get("retry_after", 2)
        time.sleep(retry_after + 0.5)
        r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def _parse_reaction(message: dict) -> str | None:
    """최우선 리액션 1개 반환. 없으면 None."""
    existing = {
        react["emoji"]["name"]: react.get("count", 0)
        for react in message.get("reactions", [])
        if react["emoji"]["name"] in REACTION_MAP and react.get("count", 0) > 0
    }
    chosen = next((e for e in PRIORITY if e in existing), None)
    return REACTION_MAP[chosen] if chosen else None


def sync_once(dry_run: bool = False) -> int:
    """
    Discord 메시지 폴링 → applied.json + pool reaction 동기화.
    리액션 제거도 감지해 null로 복원.
    반환: 변경된 건수
    """
    from job_pool import load_pool, save_pool, set_reaction

    cfg = _load_config()
    dc  = cfg.get("discord", {})
    token      = dc.get("bot_token", "")
    channel_id = dc.get("channel_id", "")

    if not token or not channel_id:
        print("[sync] bot_token 또는 channel_id 미설정 — 건너뜀")
        return 0

    history = _load_history()
    pool    = load_pool()
    applied = _load_applied()
    applied_index = {a["job_id"]: a for a in applied}

    all_records = [r for records in history.values() for r in records]
    updated = 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for record in all_records:
        job_id     = record["job_id"]
        message_id = record.get("message_id")
        if not message_id:
            continue

        try:
            msg = _get_message(token, channel_id, message_id)
            time.sleep(0.5)
        except Exception as e:
            print(f"  [sync] 메시지 조회 실패 (msg={message_id}): {e}")
            continue

        if msg is None:
            continue

        reaction = _parse_reaction(msg)

        # --- pool 업데이트 ---
        changed = set_reaction(pool, job_id, reaction, now)

        # --- applied.json 업데이트 ---
        existing = applied_index.get(job_id)

        if reaction:
            if existing:
                if existing["status"] != reaction:
                    print(f"  📝 변경: {record['company']} [{existing['status']} → {reaction}]")
                    if not dry_run:
                        existing["status"]     = reaction
                        existing["reacted_at"] = now
                    updated += 1
            else:
                entry = {
                    "job_id":        job_id,
                    "company":       record.get("company", ""),
                    "title":         record.get("title", ""),
                    "url":           record.get("url", ""),
                    "site":          record.get("site", ""),
                    "status":        reaction,
                    "reacted_at":    now,
                    "snapshot_path": record.get("snapshot_path"),
                }
                print(f"  ➕ 신규: {entry['company']} / {entry['title'][:30]} [{reaction}]")
                if not dry_run:
                    applied.append(entry)
                    applied_index[job_id] = entry
                updated += 1
        else:
            # 리액션 없음 → 기존 applied.json 항목 제거 (사용자가 실수로 눌렀다가 취소)
            if existing:
                print(f"  ➖ 리액션 제거: {existing['company']} / {existing['title'][:30]}")
                if not dry_run:
                    applied = [a for a in applied if a["job_id"] != job_id]
                    applied_index.pop(job_id, None)
                updated += 1
            elif changed:
                updated += 1

    if not dry_run:
        _save_applied(applied)
        save_pool(pool)
        if updated:
            print(f"[sync] {updated}건 반영 완료")
        else:
            print("[sync] 새로운 리액션 없음")
    else:
        print(f"[sync] dry-run — {updated}건 변경 예정")

    return updated


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print("=== 리액션 동기화 시작 ===")
    sync_once(dry_run=args.dry_run)
