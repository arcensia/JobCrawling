"""모든 크롤러를 묶어 한 번에 fetch — JobCrawler 포트 구현."""
import time


class CompositeCrawler:
    def __init__(self, config):
        self._cfg = config

    def fetch(self) -> list[dict]:
        from adapters.crawlers.wanted import fetch_wanted
        from adapters.crawlers.saramin import fetch_saramin
        from adapters.crawlers.jobkorea import fetch_jobkorea
        from adapters.crawlers.filters import matches_filter, dedupe

        cfg = self._cfg
        all_jobs = []

        if cfg.sites.get("wanted"):
            all_jobs.extend(fetch_wanted(cfg, limit=50))
            time.sleep(0.8)

        for kw in cfg.keywords:
            if cfg.sites.get("saramin"):
                all_jobs.extend(fetch_saramin(kw, cfg))
                time.sleep(0.8)
            if cfg.sites.get("jobkorea"):
                all_jobs.extend(fetch_jobkorea(kw, cfg))
                time.sleep(0.8)

        return dedupe([j for j in all_jobs if matches_filter(j, cfg)])
