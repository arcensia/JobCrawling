import time

import requests

from adapters.crawlers.filters import HEADERS
from core.config import AppConfig

WANTED_DEV_PARENT_ID = 518
WANTED_LOC = {"서울", "경기", "인천"}


def fetch_wanted(cfg: AppConfig, limit: int = 50) -> list[dict]:
    results = []
    url = "https://www.wanted.co.kr/api/chaos/navigation/v1/results"
    headers = {**HEADERS, "Referer": "https://www.wanted.co.kr/"}
    try:
        raw = []
        for offset in range(0, 301, 100):
            params = {
                "country": "kr",
                "job_sort": "job.latest_order",
                "years": "-1",
                "locations": "all",
                "limit": "100",
                "offset": str(offset),
            }
            r = requests.get(url, params=params, headers=headers, timeout=15)
            if r.status_code != 200:
                break
            data = r.json().get("data", [])
            if not data:
                break
            raw.extend(data)
            time.sleep(0.5)

        for item in raw:
            cat = item.get("category_tag") or {}
            if cat.get("parent_id") != WANTED_DEV_PARENT_ID:
                continue
            annual_from = item.get("annual_from", 99)
            annual_to = item.get("annual_to", 0)
            if annual_from > 3:
                continue
            if annual_from >= 3 and annual_to > 5:
                continue
            addr = item.get("address") or {}
            loc = addr.get("location", "")
            if loc and not any(l in loc for l in WANTED_LOC):
                continue
            pid = item.get("id")
            raw_tags = item.get("skill_tags") or []
            skills = [t.get("title", "") for t in raw_tags if isinstance(t, dict) and t.get("title")]
            results.append({
                "site": "원티드",
                "title": item.get("position", ""),
                "company": (item.get("company") or {}).get("name", ""),
                "location": loc,
                "experience": f"{item.get('annual_from', 0)}~{item.get('annual_to', '?')}년",
                "url": f"https://www.wanted.co.kr/wd/{pid}" if pid else "",
                "tags": ", ".join(skills),
            })
        print(f"[wanted] {len(results)}건 수집")
    except Exception as e:
        print(f"[wanted] 오류: {e}")
    return results[:limit]
