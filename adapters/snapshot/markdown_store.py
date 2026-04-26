"""공고 원문 Markdown 스냅샷 저장소 — SnapshotStore 포트 구현."""


class MarkdownSnapshotStore:
    def __init__(self, delay: float = 1.2):
        self._delay = delay

    def cleanup(self, retain_days: int) -> None:
        from snapshot import cleanup_old_snapshots
        cleanup_old_snapshots(retain_days=retain_days)

    def fetch_batch(self, jobs: list[dict], today: str) -> dict[str, str]:
        from snapshot import fetch_snapshots_batch
        return fetch_snapshots_batch(jobs, today=today, delay=self._delay)
