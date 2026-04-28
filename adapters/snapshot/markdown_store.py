"""공고 원문 Markdown 스냅샷 저장소 — SnapshotStore 포트 구현."""

import shutil
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from core.path import SNAPSHOTS_DIR
from domain.job import make_job_id

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

BODY_SELECTORS = {
    "원티드":   ["[class*='JobDescription']", "[class*='job-description']", "section"],
    "사람인":   [".user-content", "#job_content", ".cont_detail"],
    "잡코리아": [".posting-detail", "#duty_wrap", ".tb-recruit-group"],
}


def _slug(text: str, maxlen: int = 30) -> str:
    clean = "".join(c if c.isalnum() or c in "-_" else "_" for c in text)
    return clean[:maxlen]


def _fetch_snapshot(job: dict, today: str) -> str | None:
    url = job.get("url", "")
    if not url:
        return None

    day_dir = SNAPSHOTS_DIR / today
    day_dir.mkdir(parents=True, exist_ok=True)

    site = job.get("site", "unknown")
    company = _slug(job.get("company", "unknown"))
    jid = make_job_id(job)
    path = day_dir / f"{site}_{company}_{jid}.md"

    if path.exists():
        return str(path)

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

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


class MarkdownSnapshotStore:
    def __init__(self, delay: float = 1.2):
        self._delay = delay

    def cleanup(self, retain_days: int) -> None:
        if not SNAPSHOTS_DIR.exists():
            return
        cutoff = date.today() - timedelta(days=retain_days)
        for day_dir in SNAPSHOTS_DIR.iterdir():
            if not day_dir.is_dir():
                continue
            try:
                dir_date = date.fromisoformat(day_dir.name)
            except ValueError:
                continue
            if dir_date < cutoff:
                shutil.rmtree(day_dir)
                print(f"[snapshot] 오래된 스냅샷 삭제: {day_dir.name}")

    def fetch_batch(self, jobs: list[dict], today: str) -> dict[str, str]:
        result = {}
        for job in jobs:
            jid = make_job_id(job)
            result[jid] = _fetch_snapshot(job, today)
            time.sleep(self._delay)
        return result
