from core.config import AppConfig
from domain.filter import is_high_career

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def matches_filter(job: dict, cfg: AppConfig) -> bool:
    text = " ".join([
        job.get("title", ""), job.get("company", ""),
        job.get("location", ""), job.get("tags", ""),
    ]).lower()
    for ex in cfg.exclude_keywords:
        if ex.lower() in text:
            return False
    if is_high_career(job):
        return False
    loc = job.get("location", "")
    if loc:
        loc_ok = any(l in loc for l in cfg.locations)
        if not loc_ok:
            if not any(k in text for k in ["원격", "재택", "전국"]):
                return False
    return True


def dedupe(jobs: list) -> list:
    seen = set()
    out = []
    for j in jobs:
        key = (j.get("company", "").strip(), j.get("title", "").strip())
        if key in seen or not key[1]:
            continue
        seen.add(key)
        out.append(j)
    return out
