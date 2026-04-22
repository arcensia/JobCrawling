#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord 리액션 이벤트 봇

채용공고 메시지에 이모지를 달면 즉시 applied.json 에 반영합니다.
  ✅  지원함     → status: applied
  🎯  관심있음   → status: interested
  ❌  패스       → status: rejected

실행:
  python3 bot.py

종료:
  Ctrl+C
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import discord

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
HISTORY_PATH = BASE_DIR / "data" / "jobs_history.json"
APPLIED_PATH = BASE_DIR / "data" / "applied.json"

REACTION_MAP = {"✅": "applied", "🎯": "interested", "❌": "rejected"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("job-bot")


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_history() -> dict[str, dict]:
    """message_id → record 역인덱스로 반환"""
    if not HISTORY_PATH.exists():
        return {}
    raw = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    index = {}
    for records in raw.values():
        for r in records:
            if r.get("message_id"):
                index[str(r["message_id"])] = r
    return index


def load_applied() -> list:
    if not APPLIED_PATH.exists():
        return []
    return json.loads(APPLIED_PATH.read_text(encoding="utf-8"))


def save_applied(data: list):
    APPLIED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_applied(record: dict, status: str):
    applied = load_applied()
    job_id = record["job_id"]
    now = datetime.now(timezone.utc).isoformat()

    for entry in applied:
        if entry["job_id"] == job_id:
            if entry["status"] != status:
                entry["status"] = status
                entry["reacted_at"] = now
                save_applied(applied)
                log.info("상태 변경: %s / %s → %s", entry["company"], entry["title"][:30], status)
            return

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
    applied.append(entry)
    save_applied(applied)
    log.info("신규 기록: %s / %s [%s]", entry["company"], entry["title"][:30], status)


cfg = load_config()
dc = cfg.get("discord", {})
TARGET_CHANNEL_ID = int(dc.get("channel_id", 0))

intents = discord.Intents.default()
intents.reactions = True
intents.message_content = False  # 리액션만 볼 거라 불필요

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    log.info("봇 로그인: %s (채널 ID: %s)", client.user, TARGET_CHANNEL_ID)
    # 시작 시점에 역인덱스 한 번 로드
    client._job_index = load_history()
    log.info("공고 인덱스 로드 완료: %d건", len(client._job_index))


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # 봇 자신의 리액션 무시
    if payload.user_id == client.user.id:
        return

    # 타겟 채널 아닌 경우 무시
    if payload.channel_id != TARGET_CHANNEL_ID:
        return

    emoji = str(payload.emoji)
    if emoji not in REACTION_MAP:
        return

    msg_id = str(payload.message_id)
    job_index: dict = getattr(client, "_job_index", {})

    # 인덱스에 없으면 히스토리 재로드 (main.py 실행 후 갱신됐을 수 있음)
    if msg_id not in job_index:
        client._job_index = load_history()
        job_index = client._job_index

    if msg_id not in job_index:
        return  # 채용공고 메시지가 아님

    record = job_index[msg_id]
    status = REACTION_MAP[emoji]
    log.info("리액션 감지: %s → %s (%s)", emoji, record.get("company", "?"), status)
    upsert_applied(record, status)


@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    """리액션 제거 시 applied.json에서도 제거"""
    if payload.user_id == client.user.id:
        return
    if payload.channel_id != TARGET_CHANNEL_ID:
        return

    emoji = str(payload.emoji)
    if emoji not in REACTION_MAP:
        return

    msg_id = str(payload.message_id)
    job_index: dict = getattr(client, "_job_index", {})
    if msg_id not in job_index:
        return

    record = job_index[msg_id]
    job_id = record["job_id"]

    applied = load_applied()
    before = len(applied)
    applied = [a for a in applied if a["job_id"] != job_id]
    if len(applied) < before:
        save_applied(applied)
        log.info("리액션 제거 → applied.json에서 삭제: %s", record.get("company", "?"))


if __name__ == "__main__":
    token = dc.get("bot_token", "")
    if not token:
        print("[오류] config.json 에 bot_token 이 없습니다.")
        raise SystemExit(1)
    client.run(token, log_handler=None)
