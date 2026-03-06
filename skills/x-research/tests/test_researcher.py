"""
Unit tests for the x-research skill.

Run with:  pytest skills/x-research/tests/
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Adjust path so imports work regardless of working directory
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))  # repo root

from skills.x_research.src.storage import Storage  # noqa: E402
from skills.x_research.src.x_client import NitterClient, _extract_hashtags, _tweet_id_from_url  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Storage:
    db = Storage(tmp_path / "test.db")
    yield db
    db.close()


SAMPLE_TWEET = {
    "id": "1234567890",
    "topic": "AI news",
    "author": "testuser",
    "content": "This is a tweet about #AI and #MachineLearning!",
    "url": "https://x.com/testuser/status/1234567890",
    "likes": 42,
    "retweets": 10,
    "replies": 5,
    "hashtags": ["AI", "MachineLearning"],
    "posted_at": "2025-06-10T12:00:00",
    "source": "api",
}


# ── Storage tests ─────────────────────────────────────────────────────────────


class TestStorage:
    def test_save_and_retrieve(self, tmp_db: Storage) -> None:
        inserted = tmp_db.save_tweets([SAMPLE_TWEET])
        assert inserted == 1
        rows = tmp_db.get_recent()
        assert len(rows) == 1
        assert rows[0]["author"] == "testuser"

    def test_duplicate_ignored(self, tmp_db: Storage) -> None:
        tmp_db.save_tweets([SAMPLE_TWEET])
        inserted = tmp_db.save_tweets([SAMPLE_TWEET])
        assert inserted == 0
        assert len(tmp_db.get_recent()) == 1

    def test_filter_by_topic(self, tmp_db: Storage) -> None:
        tweet2 = {**SAMPLE_TWEET, "id": "999", "topic": "raspberry pi"}
        tmp_db.save_tweets([SAMPLE_TWEET, tweet2])
        rows = tmp_db.get_recent(topic="AI news")
        assert len(rows) == 1
        assert rows[0]["topic"] == "AI news"

    def test_top_by_engagement(self, tmp_db: Storage) -> None:
        low = {**SAMPLE_TWEET, "id": "low", "likes": 1, "retweets": 0, "replies": 0}
        high = {**SAMPLE_TWEET, "id": "high", "likes": 100, "retweets": 50, "replies": 20}
        tmp_db.save_tweets([low, high])
        top = tmp_db.get_top_by_engagement(limit=1)
        assert top[0]["id"] == "high"

    def test_trending_hashtags(self, tmp_db: Storage) -> None:
        t1 = {**SAMPLE_TWEET, "id": "t1", "hashtags": ["AI", "Tech"]}
        t2 = {**SAMPLE_TWEET, "id": "t2", "hashtags": ["AI", "Python"]}
        tmp_db.save_tweets([t1, t2])
        tags = tmp_db.get_trending_hashtags()
        tag_names = [t[0] for t in tags]
        assert "ai" in tag_names
        assert tags[0][1] == 2  # AI appears twice

    def test_purge_old(self, tmp_db: Storage) -> None:
        tmp_db.save_tweets([SAMPLE_TWEET])
        # Manually age the record
        tmp_db._conn.execute(
            "UPDATE tweets SET collected_at = datetime('now', '-60 days')"
        )
        tmp_db._conn.commit()
        purged = tmp_db.purge_old(keep_days=30)
        assert purged == 1
        assert len(tmp_db.get_recent()) == 0


# ── x_client helpers ─────────────────────────────────────────────────────────


class TestHelpers:
    def test_extract_hashtags(self) -> None:
        tags = _extract_hashtags("Hello #World and #Python3 rocks!")
        assert tags == ["World", "Python3"]

    def test_tweet_id_from_numeric_url(self) -> None:
        url = "https://x.com/user/status/1234567890"
        assert _tweet_id_from_url(url) == "1234567890"

    def test_tweet_id_from_non_numeric(self) -> None:
        url = "https://nitter.net/user/search"
        result = _tweet_id_from_url(url)
        assert len(result) == 16  # sha1 hash fallback


# ── NitterClient HTML parsing ─────────────────────────────────────────────────


NITTER_HTML = """
<html><body>
  <div class="timeline-item">
    <a class="username">@tester</a>
    <div class="tweet-content">Testing #Nitter scraping for #OpenSource</div>
    <a class="tweet-link" href="/tester/status/9876543210">#</a>
    <span class="icon-heart"></span><span>15</span>
    <span class="icon-retweet"></span><span>3</span>
    <a class="tweet-date"><a title="Jun 10, 2025 · 2:00 PM UTC">2h</a></a>
  </div>
</body></html>
"""


class TestNitterClientParsing:
    def test_parse_tweet(self) -> None:
        client = NitterClient(instances=["https://example.com"], max_results=5)
        results = client._parse_search_page(NITTER_HTML, "open source", "https://example.com")
        assert len(results) == 1
        t = results[0]
        assert t["author"] == "tester"
        assert "#Nitter" in t["content"] or "Nitter" in t["content"]
        assert "Nitter" in t["hashtags"] or "nitter" in "".join(t["hashtags"]).lower() or t["hashtags"]
        assert t["source"] == "nitter"
        client.close()
