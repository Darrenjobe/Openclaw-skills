"""
Tests for web-research skill.

Covers storage layer and helper utilities without requiring
network access or an Anthropic API key.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from src.storage import Storage
from src.searcher import _domain, _result_id


# ── Storage Tests ─────────────────────────────────────────────────────────────

class TestStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        db = Storage(tmp_path / "test.db")
        yield db
        db.close()

    def _result(self, url="https://bbc.com/news/world-1", title="BBC Article"):
        return {
            "id": _result_id(url),
            "title": title,
            "url": url,
            "source_domain": _domain(url),
            "snippet": "A brief snippet about world events.",
            "full_text": "Full article text about world events goes here.",
            "date": "2025-03-05",
        }

    def test_save_and_retrieve(self, storage):
        r = self._result()
        storage.save_results("Iran news", [r])
        results = storage.get_recent()
        assert len(results) == 1
        assert results[0]["title"] == "BBC Article"
        assert results[0]["query"] == "Iran news"

    def test_duplicate_ignored(self, storage):
        r = self._result()
        count_first = storage.save_results("Iran news", [r])
        count_second = storage.save_results("Iran news", [r])
        assert count_first == 1
        assert count_second == 0
        assert len(storage.get_recent()) == 1

    def test_filter_by_query(self, storage):
        r1 = self._result("https://bbc.com/1", "BBC Story")
        r2 = self._result("https://reuters.com/2", "Reuters Story")
        storage.save_results("Iran news", [r1])
        storage.save_results("Raspberry Pi", [r2])

        iran = storage.get_recent(query="Iran news")
        pi = storage.get_recent(query="Raspberry Pi")
        assert len(iran) == 1
        assert iran[0]["title"] == "BBC Story"
        assert len(pi) == 1
        assert pi[0]["title"] == "Reuters Story"

    def test_overall_summary_stored(self, storage):
        r = self._result()
        storage.save_results("Iran news", [r], overall_summary="Big events in Iran.")
        results = storage.get_recent()
        assert results[0]["overall_summary"] == "Big events in Iran."

    def test_purge_old_records(self, storage):
        r = self._result()
        storage.save_results("test", [r])
        # Back-date collected_at to 60 days ago
        old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        storage.conn.execute(
            "UPDATE research_results SET collected_at = ?", (old_ts,)
        )
        storage.conn.commit()

        removed = storage.purge_old(keep_days=30)
        assert removed == 1
        assert len(storage.get_recent()) == 0

    def test_purge_keeps_recent(self, storage):
        r = self._result()
        storage.save_results("test", [r])
        removed = storage.purge_old(keep_days=30)
        assert removed == 0
        assert len(storage.get_recent()) == 1

    def test_log_run(self, storage):
        run_id = storage.log_run("Iran news", "2025-03-05T00:00:00Z", 5, "Summary text")
        assert run_id is not None
        row = storage.conn.execute(
            "SELECT * FROM research_runs WHERE id = ?", (run_id,)
        ).fetchone()
        assert row["query"] == "Iran news"
        assert row["result_count"] == 5
        assert row["overall_summary"] == "Summary text"

    def test_limit_enforced(self, storage):
        for i in range(10):
            r = self._result(f"https://example.com/{i}", f"Article {i}")
            storage.save_results("test", [r])
        results = storage.get_recent(limit=3)
        assert len(results) == 3


# ── Helper Tests ──────────────────────────────────────────────────────────────

class TestHelpers:
    def test_domain_strips_www(self):
        assert _domain("https://www.bbc.com/news/article") == "bbc.com"
        assert _domain("https://reuters.com/world") == "reuters.com"
        assert _domain("https://www.aljazeera.com/news/") == "aljazeera.com"

    def test_result_id_is_stable(self):
        url = "https://example.com/article-123"
        assert _result_id(url) == _result_id(url)

    def test_result_id_length(self):
        assert len(_result_id("https://example.com/a")) == 16

    def test_result_id_unique_for_different_urls(self):
        id1 = _result_id("https://bbc.com/1")
        id2 = _result_id("https://bbc.com/2")
        assert id1 != id2

    def test_domain_with_port(self):
        assert _domain("https://localhost:8080/news") == "localhost:8080"
