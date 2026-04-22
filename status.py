#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
구직 현황 요약 출력 / Discord 발송

사용:
  python3 status.py              # 터미널 요약
  python3 status.py --send       # Discord 발송
  python3 status.py --detail     # 전체 목록 (터미널)
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import requests

BASE_DIR     = Path(__file__).parent
APPLIED_PATH = BASE_DIR / "data" / "applied.json"
POOL_PATH    = BASE_DIR / "data" / "jobs_pool.json"
CONFIG_PATH  = BASE_DIR / "config.json"

REACTION_LABEL = {
    "applied":    "✅ 지원",
    "interested": "🎯 관심",
    "rejected":   "❌ 패스",
}


def _load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_config() -> dict:
    return _load(CONFIG_PATH, {})


def _group_applied(applied: list) -> dict:
    """reaction 별로 applied 리스트 분류."""
    groups = {"applied": [], "interested": [], "rejected": []}
    for a in applied:
        s = a.get("status", "")
        if s in groups:
            groups[s].append(a)
    # 최신순 정렬
    for lst in groups.values():
        lst.sort(key=lambda x: x.get("reacted_at", ""), reverse=True)
    return groups


def _this_week_counts(applied: list) -> dict:
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    counts = {"applied": 0, "interested": 0, "rejected": 0}
    for a in applied:
        if a.get("reacted_at", "") >= cutoff:
            s = a.get("status", "")
            if s in counts:
                counts[s] += 1
    return counts


def _unreviewed_count(pool: dict) -> int:
    return sum(
        1 for e in pool.values()
        if e.get("status") == "open" and not e.get("reaction")
    )


def build_summary(detail: bool = False) -> str:
    applied = _load(APPLIED_PATH, [])
    pool    = _load(POOL_PATH, {})
    today   = datetime.now().strftime("%Y-%m-%d")

    groups      = _group_applied(applied)
    week_counts = _this_week_counts(applied)
    unreviewed  = _unreviewed_count(pool)

    lines = [f"📊 내 구직 현황 — {today}", "━" * 30]

    for status, label in REACTION_LABEL.items():
        items = groups[status]
        lines.append(f"\n{label} ({len(items)}건)")
        show = items if detail else items[:5]
        for a in show:
            date  = a.get("reacted_at", "")[:10]
            co    = a.get("company", "")[:15]
            title = a.get("title", "")[:35]
            lines.append(f"  • {date}  {co:<15}  {title}")
        if not detail and len(items) > 5:
            lines.append(f"  ... 외 {len(items) - 5}건 (--detail 로 전체 보기)")

    lines.append(
        f"\n⏰ 이번 주: 지원 {week_counts['applied']}건 / "
        f"관심 {week_counts['interested']}건 / "
        f"패스 {week_counts['rejected']}건"
    )
    lines.append(f"🆕 미검토 공고: {unreviewed}건")

    return "\n".join(lines)


def send_to_discord(webhook_url: str):
    applied = _load(APPLIED_PATH, [])
    pool    = _load(POOL_PATH, {})
    today   = datetime.now().strftime("%Y-%m-%d")

    groups      = _group_applied(applied)
    week_counts = _this_week_counts(applied)
    unreviewed  = _unreviewed_count(pool)

    def fmt_list(items: list, limit: int = 5) -> str:
        if not items:
            return "없음"
        lines = []
        for a in items[:limit]:
            date  = a.get("reacted_at", "")[:10]
            co    = a.get("company", "")[:12]
            title = a.get("title", "")[:30]
            url   = a.get("url", "")
            entry = f"`{date}` **{co}** — [{title}]({url})" if url else f"`{date}` **{co}** — {title}"
            lines.append(entry)
        if len(items) > limit:
            lines.append(f"_...외 {len(items) - limit}건_")
        return "\n".join(lines)

    fields = [
        {
            "name": f"✅ 지원 ({len(groups['applied'])}건)",
            "value": fmt_list(groups["applied"]),
            "inline": False,
        },
        {
            "name": f"🎯 관심 ({len(groups['interested'])}건)",
            "value": fmt_list(groups["interested"]),
            "inline": False,
        },
        {
            "name": "📈 이번 주",
            "value": (
                f"지원 **{week_counts['applied']}건** / "
                f"관심 **{week_counts['interested']}건** / "
                f"패스 **{week_counts['rejected']}건**"
            ),
            "inline": True,
        },
        {
            "name": "🆕 미검토 공고",
            "value": f"**{unreviewed}건** 대기 중",
            "inline": True,
        },
    ]

    payload = {
        "embeds": [{
            "title": f"📊 내 구직 현황 — {today}",
            "color": 0x57F287,
            "fields": fields,
            "footer": {"text": "python3 status.py --send"},
        }]
    }

    r = requests.post(webhook_url, json=payload, timeout=10)
    r.raise_for_status()
    print("[status] Discord 발송 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send",   action="store_true", help="Discord 발송")
    parser.add_argument("--detail", action="store_true", help="전체 목록 출력")
    args = parser.parse_args()

    if args.send:
        cfg = _load_config()
        webhook = cfg.get("discord", {}).get("webhook_url", "")
        if not webhook:
            print("[status] webhook_url 미설정")
        else:
            send_to_discord(webhook)
    else:
        print(build_summary(detail=args.detail))
