"""모든 크롤러를 묶어 한 번에 fetch — JobCrawler 포트 구현."""


class CompositeCrawler:
    def __init__(self, config):
        self._cfg = config

    def fetch(self) -> list[dict]:
        from job_bot import collect_all
        return collect_all(self._cfg)
