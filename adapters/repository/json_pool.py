"""JSON 파일 기반 풀 저장소 — JobRepository 포트 구현."""


class JsonJobRepository:
    def __init__(self, exclude_keywords: list[str] | None = None):
        self._exclude_keywords = exclude_keywords or []

    def load(self) -> dict:
        from job_pool import load_pool
        return load_pool()

    def save(self, pool: dict) -> None:
        from job_pool import save_pool
        save_pool(pool)

    def update(self, pool: dict, jobs: list[dict], today: str) -> dict:
        from job_pool import update_pool
        return update_pool(pool, jobs, today)

    def flush_closed(self, pool: dict) -> dict:
        from job_pool import flush_closed
        return flush_closed(pool)

    def candidates(self, pool: dict, mode: str, today: str) -> list[dict]:
        from job_pool import get_candidates
        return get_candidates(pool, mode=mode, today=today, exclude_keywords=self._exclude_keywords)

    def summary(self, pool: dict) -> dict:
        from job_pool import pool_summary
        return pool_summary(pool)
