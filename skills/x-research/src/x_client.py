"""
X (Twitter) data client.

Two backends:
  1. XAPIClient    — X API v2 via Bearer Token (preferred)
  2. NitterClient  — Scrapes public Nitter instances (fallback, no credentials needed)

Both return tweet dicts in a unified schema:
    {
        "id":        str,
        "topic":     str,
        "author":    str,
        "content":   str,
        "url":       str,
        "likes":     int,
        "retweets":  int,
        "replies":   int,
        "hashtags":  list[str],
        "posted_at": str | None,   # ISO-8601
        "source":    "api" | "nitter",
    }
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ── Shared helpers ────────────────────────────────────────────────────────────

_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)


def _extract_hashtags(text: str) -> list[str]:
    return _HASHTAG_RE.findall(text)


def _tweet_id_from_url(url: str) -> str:
    """Extract numeric tweet ID from a URL, or generate a hash fallback."""
    parts = url.rstrip("/").split("/")
    for part in reversed(parts):
        if part.isdigit():
            return part
    return hashlib.sha1(url.encode()).hexdigest()[:16]


# ── X API v2 Client ──────────────────────────────────────────────────────────


class XAPIClient:
    """
    Wraps the X API v2 recent-search endpoint.

    Free tier limits (as of 2025):
      - 1 request / 15 min per app
      - 500 k tweet reads / month on Basic plan
    """

    BASE_URL = "https://api.twitter.com/2"
    TWEET_FIELDS = "id,text,author_id,created_at,public_metrics,entities"
    USER_FIELDS = "username"
    EXPANSIONS = "author_id"

    def __init__(self, bearer_token: str, max_results: int = 20, result_type: str = "mixed") -> None:
        self.max_results = max(10, min(100, max_results))
        self.result_type = result_type
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=20.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=30))
    def search(self, topic: str) -> list[dict]:
        """Search recent tweets for *topic* and return normalised tweet dicts."""
        params: dict[str, Any] = {
            "query": f"{topic} lang:en -is:retweet",
            "max_results": self.max_results,
            "tweet.fields": self.TWEET_FIELDS,
            "expansions": self.EXPANSIONS,
            "user.fields": self.USER_FIELDS,
            "sort_order": "relevancy",
        }
        try:
            resp = self._client.get("/tweets/search/recent", params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("X API error %s: %s", exc.response.status_code, exc.response.text)
            raise

        body = resp.json()
        tweets_raw = body.get("data", [])
        users_by_id = {u["id"]: u["username"] for u in body.get("includes", {}).get("users", [])}

        results = []
        for t in tweets_raw:
            metrics = t.get("public_metrics", {})
            entities = t.get("entities", {})
            hashtags = [h["tag"] for h in entities.get("hashtags", [])]
            author_id = t.get("author_id", "")
            author = users_by_id.get(author_id, author_id)
            tweet_id = t["id"]
            url = f"https://x.com/{author}/status/{tweet_id}"
            results.append(
                {
                    "id": tweet_id,
                    "topic": topic,
                    "author": author,
                    "content": t.get("text", ""),
                    "url": url,
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "hashtags": hashtags,
                    "posted_at": t.get("created_at"),
                    "source": "api",
                }
            )
        logger.info("X API: fetched %d tweets for topic '%s'", len(results), topic)
        return results

    def close(self) -> None:
        self._client.close()


# ── Nitter Scraping Client ────────────────────────────────────────────────────


class NitterClient:
    """
    Scrapes public Nitter instances as a credential-free fallback.

    Nitter is an open-source Twitter frontend. Public instances may
    occasionally be rate-limited or down; the client tries each in turn.
    """

    def __init__(self, instances: list[str], max_results: int = 20) -> None:
        self.instances = [i.rstrip("/") for i in instances]
        self.max_results = max_results
        self._client = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (compatible; OpenclawBot/1.0)"},
            follow_redirects=True,
            timeout=20.0,
        )

    def search(self, topic: str) -> list[dict]:
        """Try each Nitter instance until one succeeds."""
        for instance in self.instances:
            try:
                results = self._search_instance(instance, topic)
                if results:
                    return results
            except Exception as exc:
                logger.warning("Nitter instance %s failed: %s", instance, exc)
        logger.error("All Nitter instances failed for topic '%s'", topic)
        return []

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _search_instance(self, instance: str, topic: str) -> list[dict]:
        url = f"{instance}/search"
        params = {"q": topic, "f": "tweets"}
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        return self._parse_search_page(resp.text, topic, instance)

    def _parse_search_page(self, html: str, topic: str, instance: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        tweet_items = soup.select(".timeline-item")
        results = []

        for item in tweet_items[: self.max_results]:
            try:
                results.append(self._parse_tweet(item, topic, instance))
            except Exception as exc:
                logger.debug("Failed to parse a tweet item: %s", exc)

        logger.info("Nitter (%s): scraped %d tweets for topic '%s'", instance, len(results), topic)
        return results

    def _parse_tweet(self, item: Any, topic: str, instance: str) -> dict:
        # Author
        author_tag = item.select_one(".username")
        author = author_tag.get_text(strip=True).lstrip("@") if author_tag else "unknown"

        # Content
        content_tag = item.select_one(".tweet-content")
        content = content_tag.get_text(strip=True) if content_tag else ""

        # Permalink → derive ID
        link_tag = item.select_one(".tweet-link")
        path = link_tag["href"] if link_tag and link_tag.get("href") else ""
        permalink = f"https://x.com{path}" if path else ""
        tweet_id = _tweet_id_from_url(permalink) if permalink else hashlib.sha1(content.encode()).hexdigest()[:16]

        # Stats
        def _stat(selector: str) -> int:
            tag = item.select_one(selector)
            if tag:
                raw = tag.get_text(strip=True).replace(",", "")
                try:
                    return int(raw)
                except ValueError:
                    pass
            return 0

        likes = _stat(".icon-heart + span") or _stat("[title='Likes']")
        retweets = _stat(".icon-retweet + span") or _stat("[title='Retweets']")
        replies = _stat(".icon-comment + span") or _stat("[title='Replies']")

        # Timestamp
        time_tag = item.select_one(".tweet-date a")
        posted_at: str | None = None
        if time_tag and time_tag.get("title"):
            try:
                posted_at = datetime.strptime(time_tag["title"], "%b %d, %Y · %I:%M %p %Z").isoformat()
            except ValueError:
                posted_at = time_tag.get("title")

        return {
            "id": tweet_id,
            "topic": topic,
            "author": author,
            "content": content,
            "url": permalink,
            "likes": likes,
            "retweets": retweets,
            "replies": replies,
            "hashtags": _extract_hashtags(content),
            "posted_at": posted_at,
            "source": "nitter",
        }

    def close(self) -> None:
        self._client.close()
