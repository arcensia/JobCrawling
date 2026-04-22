#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공고 원문 fetch → data/snapshots/{date}/{site}_{company}_{hash}.md 저장
"""

import hashlib
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 사이트별 본문 셀렉터
BODY_SELECTORS = {
    "원티드":   ["[class*='JobDescription']", "[class*='job-description']", "section"],
    "사람인":   [".user-content", "#job_content", ".cont_detail"],
    "잡코리아": [".posting-detail", "#duty_wrap", ".tb-recruit-group"],
}


def _slug(text: str, maxlen: int = 30) -> str:
    clean = "".join(c if c.isalnum() or c in "-_" else "_" for c in text)
    return clean[:maxlen]


def _job_id(job: dict) -> str:
    key = f"{job.get('site','')}{job.get('company','')}{job.get('title','')}"
    return hashlib.md5(key.encode()).hexdigest()[:8]


def fetch_snapshot(job: dict, today: str | None = None) -> str | None:
    """
    공고 URL에서 본문 fetch → markdown 파일로 저장.
    저장 경로 반환. 실패 시 None.
    """
    url = job.get("url", "")
    if not url:
        return None

    today = today or date.today().isoformat()
    day_dir = SNAPSHOTS_DIR / today
    day_dir.mkdir(parents=True, exist_ok=True)

    site = job.get("site", "unknown")
    company = _slug(job.get("company", "unknown"))
    jid = _job_id(job)
    filename = f"{site}_{company}_{jid}.md"
    path = day_dir / filename

    if path.exists():
        return str(path)

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # 본문 추출 시도 (사이트별 셀렉터 → fallback: body)
        body_text = ""
        for sel in BODY_SELECTORS.get(site, []):
            el = soup.select_one(sel)
            if el:
                body_text = el.get_text("\n", strip=True)
                break
        if not body_text:
            body_text = soup.get_text("\n", strip=True)[:5000]

        md = (
            f"# {job.get('title', '')}\n\n"
            f"- **회사**: {job.get('company', '')}\n"
            f"- **사이트**: {site}\n"
            f"- **지역**: {job.get('location', '')}\n"
            f"- **경력**: {job.get('experience', '')}\n"
            f"- **태그**: {job.get('tags', '')}\n"
            f"- **URL**: {url}\n"
            f"- **수집일**: {today}\n\n"
            f"---\n\n"
            f"{body_text}\n"
        )
        path.write_text(md, encoding="utf-8")
        print(f"[snapshot] 저장: {path.name}")
        return str(path)

    except Exception as e:
        print(f"[snapshot] 실패 ({company}): {e}")
        return None


def fetch_snapshots_batch(jobs: list, today: str | None = None, delay: float = 1.0) -> dict:
    """jobs 리스트 → {job_id: snapshot_path} 딕셔너리 반환"""
    today = today or date.today().isoformat()
    result = {}
    for job in jobs:
        jid = _job_id(job)
        path = fetch_snapshot(job, today)
        result[jid] = path
        time.sleep(delay)
    return result


def job_id(job: dict) -> str:
    return _job_id(job)
