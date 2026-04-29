import argparse
import json
import logging

from core.config import load_config
from core.path import APPLIED_PATH

from adapters.crawlers.composite import CompositeCrawler
from adapters.repository.json_pool import JsonJobRepository
from adapters.snapshot.markdown_store import MarkdownSnapshotStore
from adapters.ranker.keyword import KeywordRanker
from adapters.ranker.agent_with_fallback import AgentWithFallbackRanker
from adapters.ranker.ollama_ranker import OllamaRanker
from adapters.notifier.discord_webhook import DiscordWebhookNotifier
from usecase.recommend_today import RecommendJobs


def _load_applied_companies() -> list[str]:
    if not APPLIED_PATH.exists():
        return []
    applied = json.loads(APPLIED_PATH.read_text(encoding="utf-8"))
    return list({a["company"] for a in applied if a.get("status") == "applied"})


def _sync_reactions_safely() -> None:
    try:
        from adapters.sync.reaction import sync_once
        sync_once()
    except Exception:
        logging.getLogger(__name__).exception("[sync] 리액션 동기화 실패 (계속 진행)")


def main(mode: str = "today", no_rank: bool = False, ranker_type: str = "claude"):
    cfg = load_config()

    _sync_reactions_safely()

    applied = _load_applied_companies()
    if no_rank:
        ranker = KeywordRanker()
    elif ranker_type == "ollama":
        ranker = OllamaRanker(mode=mode, applied_companies=applied)
    else:
        ranker = AgentWithFallbackRanker(mode=mode, applied_companies=applied)

    usecase = RecommendJobs(
        crawler=CompositeCrawler(cfg),
        repo=JsonJobRepository(exclude_keywords=cfg.exclude_keywords),
        snapshot_store=MarkdownSnapshotStore(delay=1.2),
        ranker=ranker,
        notifier=DiscordWebhookNotifier(
            webhook_url=cfg.discord.webhook_url,
            top_n=cfg.discord.top_n,
        ),
        top_n=cfg.discord.top_n,
    )
    usecase.execute(mode=mode)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["today", "cumulative", "review"], default="today")
    parser.add_argument("--no-rank", action="store_true")
    parser.add_argument("--ranker", choices=["claude", "ollama"], default="claude")
    args = parser.parse_args()
    main(mode=args.mode, no_rank=args.no_rank, ranker_type=args.ranker)
