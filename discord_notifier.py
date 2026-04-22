#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord 웹훅 발송 + jobs_history.json 기록
- 헤더 요약 메시지 1개
- Top N 공고는 각각 개별 메시지 (리액션 추적 가능)
- 나머지는 사이트별 묶음 임베드 (참고용)
"""

import json
import time
from datetime import date
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
HISTORY_PATH = BASE_DIR / "data" / "jobs_history.json"

SITE_COLORS = {
    "원티드":   0x258BF5,
    "사람인":   0xE8380D,
    "잡코리아": 0x00C08B,
}

REACTION_GUIDE = "✅ 지원함  |  🎯 관심  |  ❌ 패스"


def _load_history() -> dict:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return {}


def _save_history(history: dict):
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _post(webhook_url: str, payload: dict) -> str | None:
    """웹훅 POST → 메시지 ID 반환 (wait=true 사용)"""
    r = requests.post(
        webhook_url,
        params={"wait": "true"},
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("id")


def send_header(webhook_url: str, total: int, top_n: int, today: str, mode_label: str = "오늘 신규"):
    payload = {
        "embeds": [{
            "title": f"📋 채용공고 추천 [{mode_label}] — {today}",
            "description": (
                f"백엔드 / 풀스택 · 주니어(1~3년) · 서울/수도권\n"
                f"후보 **{total}건** → 이력서 매칭 **Top {top_n}건** 상세 안내\n\n"
                f"{REACTION_GUIDE}"
            ),
            "color": 0x5865F2,
        }]
    }
    _post(webhook_url, payload)
    time.sleep(0.5)


def send_top_jobs(
    webhook_url: str,
    jobs: list,
    job_snapshots: dict,
    today: str | None = None,
) -> list[dict]:
    """
    Top N 공고를 각각 개별 메시지로 발송.
    반환: [{job_id, message_id, company, title, url, snapshot_path}, ...]
    """
    today = today or date.today().isoformat()
    records = []

    for i, job in enumerate(jobs, 1):
        from snapshot import job_id as make_job_id
        jid = make_job_id(job)
        site = job.get("site", "")
        color = SITE_COLORS.get(site, 0x95A5A6)

        title = job.get("title", "(제목없음)")
        company = job.get("company", "—")
        location = job.get("location", "—")
        tags = job.get("tags", "")
        url = job.get("url", "")
        snap_path = job_snapshots.get(jid)

        rank_emoji = ["🥇","🥈","🥉"] + ["🔹"] * 97
        reason = job.get("_reason", "")
        fit_points = job.get("_fit_points", [])
        red_flags = job.get("_red_flags", [])

        desc_lines = [
            f"🏢 **{company}**",
            f"📍 {location}",
        ]
        if reason:
            desc_lines.append(f"\n💡 {reason}")
        if fit_points:
            desc_lines.append("✅ " + " / ".join(fit_points[:3]))
        if red_flags:
            desc_lines.append("⚠️ " + " / ".join(red_flags[:2]))
        if tags and not fit_points:
            desc_lines.append(f"🏷 {tags[:100]}")
        if snap_path:
            desc_lines.append("💾 스냅샷 저장됨")
        desc_lines.append(f"\n{REACTION_GUIDE}")

        payload = {
            "embeds": [{
                "title": f"{rank_emoji[i-1]} [{site}] {title}",
                "url": url or None,
                "description": "\n".join(desc_lines),
                "color": color,
                "footer": {"text": f"#{i}  •  {today}"},
            }]
        }

        msg_id = _post(webhook_url, payload)
        records.append({
            "job_id": jid,
            "message_id": msg_id,
            "site": site,
            "company": company,
            "title": title,
            "url": url,
            "snapshot_path": snap_path,
        })
        time.sleep(0.5)

    return records


def send_rest_jobs(webhook_url: str, jobs: list, today: str | None = None):
    """Top N 이후 나머지 공고 — 사이트별 묶음 임베드 (참고용)"""
    today = today or date.today().isoformat()
    if not jobs:
        return

    by_site: dict[str, list] = {}
    for j in jobs:
        by_site.setdefault(j["site"], []).append(j)

    CHUNK = 10  # 임베드당 공고 수 (6000자 제한 여유있게)
    for site, items in by_site.items():
        color = SITE_COLORS.get(site, 0x95A5A6)
        for chunk_start in range(0, len(items), CHUNK):
            chunk = items[chunk_start:chunk_start + CHUNK]
            fields = []
            for j in chunk:
                url = j.get("url", "")
                title = (j.get("title", "") or "(제목없음)")[:80]
                company = (j.get("company", "") or "—")[:40]
                location = (j.get("location", "") or "—")[:50]
                value = f"🏢 {company}  📍 {location}"
                if url:
                    value += f"\n[공고 보기]({url})"
                fields.append({"name": title, "value": value, "inline": False})

            label = f"{chunk_start+1}~{chunk_start+len(chunk)}"
            payload = {
                "embeds": [{
                    "title": f"{site} 참고 공고 ({label}/{len(items)}건)",
                    "color": color,
                    "fields": fields,
                    "footer": {"text": f"참고용 • {today}"},
                }]
            }
            _post(webhook_url, payload)
            time.sleep(0.5)


def save_records(records: list, today: str | None = None):
    """jobs_history.json 에 오늘 발송 기록 저장"""
    today = today or date.today().isoformat()
    history = _load_history()
    history[today] = records
    _save_history(history)
    print(f"[history] {len(records)}건 기록 → {HISTORY_PATH}")
