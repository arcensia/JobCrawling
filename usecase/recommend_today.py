"""채용공고 추천 use case — 포트에만 의존."""

import datetime
import logging
from typing import Literal

from usecase.ports import JobCrawler, JobRepository, SnapshotStore, Ranker, Notifier

log = logging.getLogger(__name__)
Mode = Literal["today", "cumulative"]


class RecommendJobs:
    """크롤 → pool 갱신 → 후보 선정 → 랭킹 → 스냅샷 → 발송."""

    def __init__(
        self,
        crawler: JobCrawler,
        repo: JobRepository,
        snapshot_store: SnapshotStore,
        ranker: Ranker,
        notifier: Notifier,
        top_n: int,
        retain_days: int = 30,
    ):
        self._crawler = crawler
        self._repo = repo
        self._snapshots = snapshot_store
        self._ranker = ranker
        self._notifier = notifier
        self._top_n = top_n
        self._retain_days = retain_days

    def execute(self, mode: Mode) -> None:
        today = datetime.date.today().isoformat()
        log.info("=== 추천 시작 (%s) [mode=%s] ===", today, mode)

        self._snapshots.cleanup(retain_days=self._retain_days)

        all_jobs = self._crawler.fetch()
        log.info("[crawl] %d건 수집", len(all_jobs))

        pool = self._refresh_pool(all_jobs, today)

        candidates = self._repo.candidates(pool, mode=mode, today=today)
        if not candidates:
            log.info("[rank] 후보 없음 — 발송 생략")
            return
        log.info("[candidates] %d건", len(candidates))

        top_jobs, rest_jobs = self._ranker.rank(candidates, self._top_n)
        log.info("[rank] Top %d / 나머지 %d", len(top_jobs), len(rest_jobs))

        snapshots = self._snapshots.fetch_batch(top_jobs, today=today)

        self._notifier.notify_recommendations(
            top_jobs=top_jobs,
            rest_jobs=rest_jobs,
            snapshots=snapshots,
            mode_label="오늘 신규" if mode == "today" else "누적 전체",
        )

    def _refresh_pool(self, all_jobs: list[dict], today: str) -> dict:
        pool = self._repo.load()
        pool = self._repo.update(pool, all_jobs, today)
        pool = self._repo.flush_closed(pool)
        s = self._repo.summary(pool)
        log.info(
            "[pool] open=%d / 지원=%d / 관심=%d / 전체=%d",
            s.get("open", 0), s.get("applied", 0), s.get("interested", 0), len(pool),
        )
        self._repo.save(pool)
        return pool
