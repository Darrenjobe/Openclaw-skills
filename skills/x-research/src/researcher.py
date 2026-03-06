"""
Research orchestrator for the x-research skill.

Coordinates the X client (API or Nitter), storage, and JSON export.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .storage import Storage
from .x_client import NitterClient, XAPIClient

logger = logging.getLogger(__name__)


class Researcher:
    def __init__(self, config: dict, skill_root: Path) -> None:
        self.config = config
        self.skill_root = skill_root
        self.topics: list[str] = config.get("topics", [])

        # Storage
        storage_cfg = config.get("storage", {})
        db_path = skill_root / storage_cfg.get("db_path", "data/x_research.db")
        self.storage = Storage(db_path)
        self.export_json: bool = storage_cfg.get("export_json", True)
        self.export_dir = skill_root / storage_cfg.get("export_dir", "data/exports")
        self.keep_days: int = storage_cfg.get("keep_days", 30)

        # Client selection
        api_cfg = config.get("x_api", {})
        bearer_token: str = api_cfg.get("bearer_token", "").strip()

        if bearer_token:
            logger.info("Using X API v2 backend")
            self.client = XAPIClient(
                bearer_token=bearer_token,
                max_results=api_cfg.get("max_results", 20),
                result_type=api_cfg.get("result_type", "mixed"),
            )
            self.source = "api"
        else:
            nitter_cfg = config.get("nitter", {})
            instances: list[str] = nitter_cfg.get("instances", [])
            if not instances:
                raise ValueError(
                    "No X API bearer_token and no Nitter instances configured. "
                    "Set at least one in config.yaml."
                )
            logger.info("No API key found — using Nitter scraping fallback")
            self.client = NitterClient(
                instances=instances,
                max_results=nitter_cfg.get("max_results", 20),
            )
            self.source = "nitter"

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self, topics: list[str] | None = None) -> dict:
        """
        Execute a research run.

        Args:
            topics: Override topics from config for this run.

        Returns:
            Summary dict with per-topic results and top trends.
        """
        topics_to_run = topics or self.topics
        if not topics_to_run:
            raise ValueError("No topics configured. Add topics to config.yaml or pass --topic on the CLI.")

        started_at = datetime.now(timezone.utc).isoformat()
        logger.info("Starting research run — topics: %s", topics_to_run)

        all_tweets: list[dict] = []
        per_topic: dict[str, list[dict]] = {}

        for topic in topics_to_run:
            logger.info("Researching topic: '%s'", topic)
            try:
                tweets = self.client.search(topic)
            except Exception as exc:
                logger.error("Failed to fetch tweets for '%s': %s", topic, exc)
                tweets = []
            per_topic[topic] = tweets
            all_tweets.extend(tweets)

        # Persist
        inserted = self.storage.save_tweets(all_tweets)
        finished_at = datetime.now(timezone.utc).isoformat()
        self.storage.log_run(started_at, finished_at, topics_to_run, inserted, self.source)

        # Purge old records
        if self.keep_days > 0:
            purged = self.storage.purge_old(self.keep_days)
            if purged:
                logger.info("Purged %d old tweets (keep_days=%d)", purged, self.keep_days)

        # Build summary
        summary = self._build_summary(topics_to_run, per_topic, started_at, finished_at, inserted)

        # Export JSON
        if self.export_json:
            self._export_json(summary, started_at)

        logger.info(
            "Run complete — %d tweets fetched, %d new stored", len(all_tweets), inserted
        )
        return summary

    # ── Summary & export ─────────────────────────────────────────────────────

    def _build_summary(
        self,
        topics: list[str],
        per_topic: dict[str, list[dict]],
        started_at: str,
        finished_at: str,
        new_count: int,
    ) -> dict:
        summary: dict = {
            "run": {
                "started_at": started_at,
                "finished_at": finished_at,
                "source": self.source,
                "new_tweets_stored": new_count,
            },
            "topics": {},
        }

        for topic, tweets in per_topic.items():
            top_tweets = sorted(
                tweets,
                key=lambda t: t.get("retweets", 0) * 2 + t.get("likes", 0) + t.get("replies", 0),
                reverse=True,
            )[:5]

            # Hashtag frequency within this run
            tag_counts: dict[str, int] = {}
            for t in tweets:
                for tag in t.get("hashtags", []):
                    key = tag.lower()
                    tag_counts[key] = tag_counts.get(key, 0) + 1
            trending_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            summary["topics"][topic] = {
                "tweet_count": len(tweets),
                "top_tweets": [
                    {
                        "author": t["author"],
                        "content": t["content"][:280],
                        "url": t["url"],
                        "likes": t.get("likes", 0),
                        "retweets": t.get("retweets", 0),
                        "replies": t.get("replies", 0),
                    }
                    for t in top_tweets
                ],
                "trending_hashtags": [{"tag": tag, "count": cnt} for tag, cnt in trending_tags],
            }

        return summary

    def _export_json(self, summary: dict, started_at: str) -> None:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        # Filename: exports/2025-06-10T14-30-00Z.json
        ts = started_at.replace(":", "-").replace("+", "Z").split(".")[0] + "Z"
        export_path = self.export_dir / f"{ts}.json"
        export_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        logger.info("Exported summary to %s", export_path)

    # ── Query helpers ─────────────────────────────────────────────────────────

    def recent(self, topic: str | None = None, limit: int = 20) -> list[dict]:
        return self.storage.get_recent(topic=topic, limit=limit)

    def top(self, topic: str | None = None, limit: int = 10) -> list[dict]:
        return self.storage.get_top_by_engagement(topic=topic, limit=limit)

    def trending_hashtags(self, topic: str | None = None, limit: int = 10) -> list[tuple[str, int]]:
        return self.storage.get_trending_hashtags(topic=topic, limit=limit)

    def close(self) -> None:
        self.client.close()
        self.storage.close()
