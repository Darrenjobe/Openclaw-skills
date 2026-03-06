"""
Orchestration layer: search → scrape → summarize → store → export.
"""

import json
from datetime import datetime, timezone
from logging import Logger
from pathlib import Path

from src.searcher import get_searcher
from src.summarizer import get_summarizer
from src.storage import Storage
from shared.utils import ensure_dir


class WebResearcher:
    def __init__(self, config: dict, skill_root: Path, logger: Logger):
        self.config = config
        self.skill_root = skill_root
        self.logger = logger

        db_path = skill_root / config.get("storage", {}).get(
            "db_path", "data/web_research.db"
        )
        ensure_dir(db_path.parent)

        self.searcher = get_searcher(config)
        self.summarizer = get_summarizer(config)
        self.storage = Storage(db_path)

    def run(self, queries: list[str]) -> dict:
        """
        Execute a full research pass for each query.

        Returns a summary dict suitable for JSON export or terminal display.
        """
        started_at = datetime.now(timezone.utc).isoformat()
        output: dict = {"started_at": started_at, "queries": {}}

        for query in queries:
            self.logger.info("Researching: %s", query)
            results = self.searcher.search_and_scrape(query)
            self.logger.info("Fetched %d results for '%s'", len(results), query)

            overall_summary = ""
            if results:
                try:
                    overall_summary = self.summarizer.summarize(query, results)
                except Exception as exc:
                    self.logger.error("Summarization failed for '%s': %s", query, exc)
                    overall_summary = f"[Summarization unavailable: {exc}]"

            self.storage.save_results(query, results, overall_summary)
            self.storage.log_run(query, started_at, len(results), overall_summary)

            output["queries"][query] = {
                "result_count": len(results),
                "overall_summary": overall_summary,
                "results": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "source_domain": r.get("source_domain", ""),
                        "snippet": r.get("snippet", ""),
                        "date": r.get("date", ""),
                    }
                    for r in results
                ],
            }

        if self.config.get("storage", {}).get("export_json"):
            self._export_json(output)

        keep_days = self.config.get("storage", {}).get("keep_days", 30)
        if keep_days > 0:
            removed = self.storage.purge_old(keep_days)
            if removed:
                self.logger.info("Purged %d old records", removed)

        return output

    def recent(self, query: str | None = None, limit: int = 20) -> list[dict]:
        return self.storage.get_recent(query=query, limit=limit)

    def _export_json(self, data: dict):
        export_dir = self.skill_root / self.config.get("storage", {}).get(
            "export_dir", "data/exports"
        )
        ensure_dir(export_dir)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = export_dir / f"web_research_{ts}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self.logger.info("Exported results to %s", path)

    def close(self):
        if hasattr(self.searcher, "close"):
            self.searcher.close()
        if hasattr(self.summarizer, "close"):
            self.summarizer.close()
        self.storage.close()
