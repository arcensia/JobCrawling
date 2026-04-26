#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주간 이력서 갭 분석

지난 N일간 수집된 공고 스냅샷에서 기술 키워드 빈도를 집계하고,
이력서와 비교해 부족한 키워드를 Discord로 리포트합니다.

실행:
  python3 resume_gap.py            # 분석 결과만 출력
  python3 resume_gap.py --send     # 분석 + Discord 발송
  python3 resume_gap.py --days 14  # 기간 조정 (기본 7일)
"""

import argparse
import json
import re
import time
from collections import Counter
from datetime import date, timedelta
import requests

from core.path import SNAPSHOTS_DIR, RESUME_DIR, CONFIG_PATH

# 분석 대상 기술 키워드 목록
TECH_KEYWORDS = [
    # 언어
    "python", "java", "kotlin", "node.js", "nodejs", "typescript", "go", "golang", "rust", "c#",
    # 프레임워크
    "fastapi", "spring", "spring boot", "django", "flask", "express", "nestjs", "nest.js",
    # 데이터베이스
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra", "dynamodb",
    "mssql", "oracle", "sqlite",
    # 메시징
    "kafka", "rabbitmq", "sqs", "pubsub",
    # 인프라
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure", "terraform", "ansible",
    "nginx", "linux",
    # CI/CD
    "gitlab", "github actions", "jenkins", "ci/cd", "cicd",
    # 패턴/개념
    "msa", "microservice", "rest api", "restful", "grpc", "graphql",
    "비동기", "async", "celery", "event driven",
    # 모니터링
    "grafana", "prometheus", "datadog", "sentry",
]


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_resume() -> str:
    parts = []
    for fname in ["이력서.txt", "경력기술서.txt"]:
        p = RESUME_DIR / fname
        if p.exists():
            parts.append(p.read_text(encoding="utf-8").lower())
    return " ".join(parts)


def collect_snapshots(days: int = 7) -> list[str]:
    """최근 N일 스냅샷 텍스트 목록 반환"""
    texts = []
    today = date.today()
    for i in range(days):
        target = (today - timedelta(days=i)).isoformat()
        day_dir = SNAPSHOTS_DIR / target
        if not day_dir.exists():
            continue
        for md_file in day_dir.glob("*.md"):
            texts.append(md_file.read_text(encoding="utf-8").lower())
    return texts


def count_keywords(texts: list[str]) -> Counter:
    """공고 텍스트에서 기술 키워드 빈도 집계"""
    counter = Counter()
    for text in texts:
        for kw in TECH_KEYWORDS:
            if kw in text:
                counter[kw] += 1
    return counter


def analyze(days: int = 7) -> dict:
    resume_text = load_resume()
    snapshots = collect_snapshots(days)
    total = len(snapshots)

    if total == 0:
        return {"total": 0, "days": days, "gaps": [], "have": []}

    freq = count_keywords(snapshots)

    gaps = []   # 공고엔 많이 나오지만 이력서에 없는 것
    have = []   # 공고에도 나오고 이력서에도 있는 것

    for kw, count in freq.most_common():
        pct = round(count / total * 100)
        if pct < 10:  # 10% 미만은 노이즈
            continue
        in_resume = kw in resume_text
        entry = {"keyword": kw, "count": count, "total": total, "pct": pct}
        if in_resume:
            have.append(entry)
        else:
            gaps.append(entry)

    return {
        "total": total,
        "days": days,
        "period_start": (date.today() - timedelta(days=days - 1)).isoformat(),
        "period_end": date.today().isoformat(),
        "gaps": gaps[:15],   # 상위 15개
        "have": have[:10],
    }


def format_report(result: dict) -> str:
    """터미널 출력용 텍스트"""
    lines = [
        f"=== 이력서 갭 분석 ({result['period_start']} ~ {result['period_end']}) ===",
        f"분석 공고 수: {result['total']}건 ({result['days']}일)",
        "",
        "🔴 이력서에 없는데 공고에 자주 등장 (갭)",
    ]
    for g in result["gaps"]:
        lines.append(f"  {g['keyword']:20s} {g['count']:3d}/{g['total']}건 ({g['pct']}%)")

    lines += ["", "✅ 이력서에도 있고 공고에도 자주 등장 (강점)"]
    for h in result["have"]:
        lines.append(f"  {h['keyword']:20s} {h['count']:3d}/{h['total']}건 ({h['pct']}%)")

    return "\n".join(lines)


def send_discord(result: dict, insight: str = ""):
    cfg = load_config()
    webhook_url = cfg.get("discord", {}).get("webhook_url", "")
    if not webhook_url:
        print("[discord] webhook_url 미설정")
        return

    today = date.today().isoformat()
    period = f"{result['period_start']} ~ {result['period_end']}"

    # 갭 필드
    gap_lines = []
    for g in result["gaps"][:8]:
        bar = "█" * (g["pct"] // 10) + "░" * (10 - g["pct"] // 10)
        gap_lines.append(f"`{g['keyword']:18s}` {bar} {g['pct']}% ({g['count']}/{g['total']}건)")

    # 강점 필드
    have_lines = []
    for h in result["have"][:6]:
        have_lines.append(f"`{h['keyword']:18s}` {h['pct']}% ({h['count']}/{h['total']}건)")

    embeds = [{
        "title": f"📊 주간 이력서 갭 분석 — {today}",
        "description": (
            f"**{period}** 동안 수집된 공고 **{result['total']}건** 분석\n"
            f"이력서에 없는데 공고에 자주 등장하는 기술을 확인하세요."
        ),
        "color": 0xF59E0B,
        "fields": [
            {
                "name": "🔴 이력서 갭 (추가 검토 필요)",
                "value": "\n".join(gap_lines) if gap_lines else "없음",
                "inline": False,
            },
            {
                "name": "✅ 이력서 강점 (공고 매칭 중)",
                "value": "\n".join(have_lines) if have_lines else "없음",
                "inline": False,
            },
        ],
        "footer": {"text": f"분석 기간 {result['days']}일  •  python3 resume_gap.py --send 로 재실행"},
    }]

    if insight:
        embeds[0]["fields"].append({
            "name": "💡 Claude 인사이트",
            "value": insight[:1000],
            "inline": False,
        })

    r = requests.post(webhook_url, json={"embeds": embeds}, timeout=10)
    r.raise_for_status()
    print(f"[discord] 갭 분석 리포트 발송 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Discord로 발송")
    parser.add_argument("--days", type=int, default=7, help="분석 기간 (기본 7일)")
    parser.add_argument("--insight", type=str, default="", help="Claude 인사이트 텍스트 (옵션)")
    args = parser.parse_args()

    result = analyze(days=args.days)

    if result["total"] == 0:
        print(f"[gap] 최근 {args.days}일간 스냅샷이 없습니다. main.py 를 먼저 실행하세요.")
    else:
        print(format_report(result))
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if args.send:
            send_discord(result, insight=args.insight)
