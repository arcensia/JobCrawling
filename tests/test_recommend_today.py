"""use case 단위 테스트 — fake 객체만 사용. monkeypatch 없음."""

from usecase.recommend_today import RecommendJobs


class FakeCrawler:
    def __init__(self, jobs=None):
        self._jobs = jobs or []

    def fetch(self):
        return list(self._jobs)


class FakeRepo:
    def __init__(self, candidates=None):
        self._candidates = candidates or []
        self.saved = None

    def load(self):
        return {}

    def save(self, pool):
        self.saved = pool

    def update(self, pool, jobs, today):
        return pool

    def flush_closed(self, pool):
        return pool

    def candidates(self, pool, mode, today):
        return list(self._candidates)

    def summary(self, pool):
        return {"open": len(self._candidates), "applied": 0, "interested": 0}


class FakeSnapshotStore:
    def __init__(self):
        self.cleaned_with = None
        self.fetched_for = None

    def cleanup(self, retain_days):
        self.cleaned_with = retain_days

    def fetch_batch(self, jobs, today):
        self.fetched_for = jobs
        return {f"job-{i}": "/tmp/snap.md" for i in range(len(jobs))}


class FakeRanker:
    def rank(self, jobs, top_n):
        return jobs[:top_n], jobs[top_n:]


class FakeNotifier:
    def __init__(self):
        self.called_with = None

    def notify_recommendations(self, **kwargs):
        self.called_with = kwargs


def _make(usecase_kwargs=None, **overrides):
    defaults = dict(
        crawler=FakeCrawler(),
        repo=FakeRepo(),
        snapshot_store=FakeSnapshotStore(),
        ranker=FakeRanker(),
        notifier=FakeNotifier(),
        top_n=3,
    )
    defaults.update(overrides)
    return RecommendJobs(**defaults), defaults


def test_no_candidates_skips_notification():
    usecase, deps = _make()
    usecase.execute(mode="today")
    assert deps["notifier"].called_with is None


def test_candidates_trigger_notification():
    candidates = [{"site": "원티드", "title": f"백엔드 {i}"} for i in range(5)]
    notifier = FakeNotifier()
    usecase, deps = _make(repo=FakeRepo(candidates=candidates), notifier=notifier)

    usecase.execute(mode="today")

    assert notifier.called_with is not None
    assert len(notifier.called_with["top_jobs"]) == 3
    assert len(notifier.called_with["rest_jobs"]) == 2
    assert notifier.called_with["mode_label"] == "오늘 신규"


def test_cumulative_mode_label():
    candidates = [{"title": "x"}]
    notifier = FakeNotifier()
    usecase, _ = _make(repo=FakeRepo(candidates=candidates), notifier=notifier)
    usecase.execute(mode="cumulative")
    assert notifier.called_with["mode_label"] == "누적 전체"


def test_snapshot_cleanup_runs():
    snapshots = FakeSnapshotStore()
    usecase, _ = _make(snapshot_store=snapshots)
    usecase.execute(mode="today")
    assert snapshots.cleaned_with == 30
