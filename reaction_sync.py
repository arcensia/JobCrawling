#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord 리액션 폴링 → applied.json 동기화

리액션 의미:
  ✅  지원함     → status: applied
  🎯  관심있음   → status: interested
  ❌  패스       → status: rejected

실행:
  python3 reaction_sync.py
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
HISTORY_PATH = BASE_DIR / "data" / "jobs_history.json"
APPLIED_PATH = BASE_DIR / "data" / "applied.json"
CONFIG_PATH = BASE_DIR / "config.json"

REACTION_MAP = {
    "✅": "applied",
    "🎯": "interested",
    "❌": "rejected",
}


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def load_applied() -> list:
    if not APPLIED_PATH.exists():
        return []
    return json.loads(APPLIED_PATH.read_text(encoding="utf-8"))


def save_applied(data: list):
    APPLIED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_message(token: str, channel_id: str, message_id: str) -> dict | None:
    """메시지 1건 fetch — reactions 필드에 모든 이모지 포함"""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    headers = {"Authorization": f"Bot {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 404:
        return None
    if r.status_code == 429:
        retry_after = r.json().get("retry_after", 2)
        print(f"  [rate limit] {retry_after}s 대기...")
        time.sleep(retry_after + 0.5)
        r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def parse_reactions(message: dict) -> dict[str, str]:
    """메시지의 reactions 필드 → {emoji: status} 중 REACTION_MAP 해당 항목만"""
    result = {}
    for react in message.get("reactions", []):
        emoji_name = react.get("emoji", {}).get("name", "")
        if emoji_name in REACTION_MAP and react.get("count", 0) > 0:
            result[emoji_name] = REACTION_MAP[emoji_name]
    return result


def sync(dry_run: bool = False):
    cfg = load_config()
    dc = cfg.get("discord", {})
    token = dc.get("bot_token", "")
    channel_id = dc.get("channel_id", "")

    if not token or not channel_id:
        print("[sync] bot_token 또는 channel_id 미설정")
        return

    history = load_history()
    applied = load_applied()
    applied_index = {a["job_id"]: a for a in applied}

    updated = 0
    now = datetime.now(timezone.utc).isoformat()

    all_records = [r for records in history.values() for r in records]

    for record in all_records:
        job_id = record["job_id"]
        message_id = record.get("message_id")
        if not message_id:
            continue

        try:
            msg = get_message(token, channel_id, message_id)
            time.sleep(0.8)
        except Exception as e:
            print(f"[sync] 메시지 조회 실패 (msg={message_id}): {e}")
            continue

        if not msg:
            continue

        reacted = parse_reactions(msg)
        if not reacted:
            continue

        # 여러 이모지 달려있으면 우선순위: applied > interested > rejected
        priority = ["✅", "🎯", "❌"]
        chosen_emoji = next((e for e in priority if e in reacted), None)
        if not chosen_emoji:
            continue
        status = reacted[chosen_emoji]

        existing = applied_index.get(job_id)
        if existing:
            if existing["status"] != status:
                print(f"  📝 상태 변경: {record['company']} / {record['title'][:30]} → {status}")
                if not dry_run:
                    existing["status"] = status
                    existing["reacted_at"] = now
                updated += 1
        else:
            entry = {
                "job_id": job_id,
                "company": record.get("company", ""),
                "title": record.get("title", ""),
                "url": record.get("url", ""),
                "site": record.get("site", ""),
                "status": status,
                "reacted_at": now,
                "snapshot_path": record.get("snapshot_path"),
            }
            print(f"  ➕ 신규: {entry['company']} / {entry['title'][:30]} [{status}]")
            if not dry_run:
                applied.append(entry)
                applied_index[job_id] = entry
            updated += 1

    if not dry_run and updated:
        save_applied(applied)
        print(f"\n[sync] {updated}건 반영 → {APPLIED_PATH}")
    elif not updated:
        print("[sync] 새로운 리액션 없음")
    else:
        print(f"\n[sync] dry-run — {updated}건 변경 예정 (실제 저장 안 함)")

    return updated


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="변경 내용만 출력, 저장 안 함")
    args = parser.parse_args()
    print(f"=== 리액션 동기화 시작 ===")
    sync(dry_run=args.dry_run)
