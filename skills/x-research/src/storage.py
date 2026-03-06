"""
SQLite storage layer for the x-research skill.

Schema
------
tweets
  id            TEXT PRIMARY KEY   -- tweet ID from X or a hash for scraped tweets
  topic         TEXT               -- the research topic this tweet was found under
  author        TEXT               -- username / handle
  content       TEXT               -- full tweet text
  url           TEXT               -- permalink
  likes         INTEGER
  retweets      INTEGER
  replies       INTEGER
  hashtags      TEXT               -- comma-separated
  collected_at  TEXT               -- ISO-8601 timestamp of when WE collected it
  posted_at     TEXT               -- ISO-8601 timestamp from X (may be NULL for scraped)
  source        TEXT               -- "api" or "nitter"

runs
  id            INTEGER PRIMARY KEY AUTOINCREMENT
  started_at    TEXT
  finished_at   TEXT
  topics        TEXT               -- JSON array of topics searched
  tweet_count   INTEGER
  source        TEXT
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _migrate(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS tweets (
                id           TEXT PRIMARY KEY,
                topic        TEXT NOT NULL,
                author       TEXT,
                content      TEXT,
                url          TEXT,
                likes        INTEGER DEFAULT 0,
                retweets     INTEGER DEFAULT 0,
                replies      INTEGER DEFAULT 0,
                hashtags     TEXT,
                collected_at TEXT NOT NULL,
                posted_at    TEXT,
                source       TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tweets_topic        ON tweets(topic);
            CREATE INDEX IF NOT EXISTS idx_tweets_collected_at ON tweets(collected_at);

            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TEXT NOT NULL,
                finished_at TEXT,
                topics      TEXT,
                tweet_count INTEGER DEFAULT 0,
                source      TEXT
            );
        """)
        self._conn.commit()

    # ── Writes ────────────────────────────────────────────────────────────────

    def save_tweets(self, tweets: list[dict]) -> int:
        """
        Upsert a list of tweet dicts. Returns number of new rows inserted.
        """
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        for t in tweets:
            try:
                cur = self._conn.execute(
                    """
                    INSERT OR IGNORE INTO tweets
                        (id, topic, author, content, url, likes, retweets,
                         replies, hashtags, collected_at, posted_at, source)
                    VALUES
                        (:id, :topic, :author, :content, :url, :likes, :retweets,
                         :replies, :hashtags, :collected_at, :posted_at, :source)
                    """,
                    {
                        "id": t.get("id", ""),
                        "topic": t.get("topic", ""),
                        "author": t.get("author", ""),
                        "content": t.get("content", ""),
                        "url": t.get("url", ""),
                        "likes": t.get("likes", 0),
                        "retweets": t.get("retweets", 0),
                        "replies": t.get("replies", 0),
                        "hashtags": ",".join(t.get("hashtags", [])),
                        "collected_at": now,
                        "posted_at": t.get("posted_at"),
                        "source": t.get("source", "unknown"),
                    },
                )
                inserted += cur.rowcount
            except sqlite3.Error as exc:
                logger.warning("Failed to insert tweet %s: %s", t.get("id"), exc)
        self._conn.commit()
        return inserted

    def log_run(self, started_at: str, finished_at: str, topics: list[str], tweet_count: int, source: str) -> None:
        self._conn.execute(
            """
            INSERT INTO runs (started_at, finished_at, topics, tweet_count, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (started_at, finished_at, json.dumps(topics), tweet_count, source),
        )
        self._conn.commit()

    # ── Reads ────────────────────────────────────────────────────────────────

    def get_recent(self, topic: str | None = None, limit: int = 50) -> list[dict]:
        """Return most-recently collected tweets, optionally filtered by topic."""
        if topic:
            rows = self._conn.execute(
                "SELECT * FROM tweets WHERE topic = ? ORDER BY collected_at DESC LIMIT ?",
                (topic, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tweets ORDER BY collected_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_top_by_engagement(self, topic: str | None = None, limit: int = 10) -> list[dict]:
        """Return tweets ranked by (retweets * 2 + likes + replies)."""
        base = "SELECT *, (retweets * 2 + likes + replies) AS score FROM tweets"
        if topic:
            rows = self._conn.execute(
                base + " WHERE topic = ? ORDER BY score DESC LIMIT ?", (topic, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(base + " ORDER BY score DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_trending_hashtags(self, topic: str | None = None, limit: int = 10) -> list[tuple[str, int]]:
        """Return (hashtag, count) sorted by frequency across stored tweets."""
        if topic:
            rows = self._conn.execute(
                "SELECT hashtags FROM tweets WHERE topic = ? AND hashtags != ''", (topic,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT hashtags FROM tweets WHERE hashtags != ''").fetchall()

        counts: dict[str, int] = {}
        for row in rows:
            for tag in row["hashtags"].split(","):
                tag = tag.strip().lower()
                if tag:
                    counts[tag] = counts.get(tag, 0) + 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    # ── Maintenance ───────────────────────────────────────────────────────────

    def purge_old(self, keep_days: int) -> int:
        """Delete tweets collected more than keep_days ago. Returns deleted count."""
        if keep_days <= 0:
            return 0
        cur = self._conn.execute(
            "DELETE FROM tweets WHERE collected_at < datetime('now', ?)",
            (f"-{keep_days} days",),
        )
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()
