"""
SQLite persistence for web research results.

Schema:
  research_results — one row per scraped article, keyed by URL hash
  research_runs    — one row per run (query + timestamp + overall summary)
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path


class Storage:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS research_results (
                id            TEXT PRIMARY KEY,
                query         TEXT NOT NULL,
                title         TEXT,
                url           TEXT NOT NULL,
                source_domain TEXT,
                snippet       TEXT,
                full_text     TEXT,
                overall_summary TEXT,
                date          TEXT,
                collected_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS research_runs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                query           TEXT NOT NULL,
                started_at      TEXT NOT NULL,
                finished_at     TEXT,
                result_count    INTEGER,
                overall_summary TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_results_query
                ON research_results(query);
            CREATE INDEX IF NOT EXISTS idx_results_collected
                ON research_results(collected_at);
        """)
        self.conn.commit()

    def save_results(self, query: str, results: list[dict], overall_summary: str = "") -> int:
        """Upsert results; returns count of newly inserted rows."""
        now = datetime.now(timezone.utc).isoformat()
        new_count = 0
        for r in results:
            try:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO research_results
                        (id, query, title, url, source_domain, snippet,
                         full_text, overall_summary, date, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.get("id", ""),
                        query,
                        r.get("title", ""),
                        r.get("url", ""),
                        r.get("source_domain", ""),
                        r.get("snippet", ""),
                        r.get("full_text", ""),
                        overall_summary,
                        r.get("date", ""),
                        now,
                    ),
                )
                if self.conn.execute("SELECT changes()").fetchone()[0]:
                    new_count += 1
            except sqlite3.Error:
                pass
        self.conn.commit()
        return new_count

    def log_run(
        self,
        query: str,
        started_at: str,
        result_count: int,
        overall_summary: str,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO research_runs
                (query, started_at, finished_at, result_count, overall_summary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                query,
                started_at,
                datetime.now(timezone.utc).isoformat(),
                result_count,
                overall_summary,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_recent(self, query: str | None = None, limit: int = 20) -> list[dict]:
        if query:
            rows = self.conn.execute(
                """SELECT * FROM research_results
                   WHERE query = ?
                   ORDER BY collected_at DESC LIMIT ?""",
                (query, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT * FROM research_results
                   ORDER BY collected_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def purge_old(self, keep_days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
        cur = self.conn.execute(
            "DELETE FROM research_results WHERE collected_at < ?", (cutoff,)
        )
        self.conn.commit()
        return cur.rowcount

    def close(self):
        self.conn.close()
