"""
Web search and page scraping backends.

Two backends are supported:
  - DuckDuckGoSearcher: free, no API key required (default)
  - BraveSearcher: Brave Search API, free tier 2000 req/month

Both backends use trafilatura for clean article text extraction —
no browser or display required, works headlessly on Raspberry Pi.
"""

import hashlib
from urllib.parse import urlparse

import trafilatura

from shared.utils import setup_logging

logger = setup_logging("web-research.searcher")


def _domain(url: str) -> str:
    """Extract bare domain from a URL."""
    return urlparse(url).netloc.replace("www.", "")


def _result_id(url: str) -> str:
    """Stable 16-char ID derived from a URL."""
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _fetch_page_text(url: str, max_chars: int = 8000) -> str | None:
    """Fetch a URL and extract clean article text using trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
        )
        if text and len(text) > max_chars:
            text = text[:max_chars] + "…"
        return text
    except Exception as exc:
        logger.debug("Failed to fetch %s: %s", url, exc)
        return None


class DuckDuckGoSearcher:
    """
    Search using DuckDuckGo — no API key, no registration required.
    Uses the duckduckgo-search library (DDGS) which calls the DDG API.
    """

    def __init__(self, config: dict):
        srch = config.get("search", {})
        scr = config.get("scraping", {})
        self.max_results = srch.get("max_results", 8)
        self.safe_search = srch.get("safe_search", "moderate")
        self.news_mode = srch.get("news_mode", True)
        self.max_chars = scr.get("max_content_chars", 8000)

    def search(self, query: str) -> list[dict]:
        """Return raw search result dicts from DuckDuckGo."""
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            if self.news_mode:
                raw = list(ddgs.news(query, max_results=self.max_results))
                for r in raw:
                    url = r.get("url", r.get("href", ""))
                    results.append({
                        "id": _result_id(url),
                        "title": r.get("title", ""),
                        "url": url,
                        "snippet": r.get("body", ""),
                        "source_domain": r.get("source", _domain(url)),
                        "date": r.get("date", ""),
                    })
            else:
                raw = list(ddgs.text(
                    query,
                    max_results=self.max_results,
                    safesearch=self.safe_search,
                ))
                for r in raw:
                    url = r.get("href", "")
                    results.append({
                        "id": _result_id(url),
                        "title": r.get("title", ""),
                        "url": url,
                        "snippet": r.get("body", ""),
                        "source_domain": _domain(url),
                        "date": "",
                    })
        return results

    def search_and_scrape(self, query: str) -> list[dict]:
        """Search + fetch full page text for each result."""
        results = self.search(query)
        for r in results:
            if r.get("url"):
                r["full_text"] = _fetch_page_text(r["url"], self.max_chars)
        return results


class BraveSearcher:
    """
    Search using the Brave Search API.
    Free tier: 2000 queries/month — https://brave.com/search/api/
    Requires brave_api_key in config.yaml search section.
    """

    _BASE = "https://api.search.brave.com/res/v1"

    def __init__(self, config: dict):
        import httpx
        srch = config.get("search", {})
        scr = config.get("scraping", {})
        self.api_key = srch.get("brave_api_key", "")
        self.max_results = srch.get("max_results", 8)
        self.news_mode = srch.get("news_mode", True)
        self.timeout = scr.get("timeout", 15)
        self.max_chars = scr.get("max_content_chars", 8000)
        self._http = httpx.Client(timeout=self.timeout)

    def search(self, query: str) -> list[dict]:
        endpoint = (
            f"{self._BASE}/news/search" if self.news_mode
            else f"{self._BASE}/web/search"
        )
        resp = self._http.get(
            endpoint,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.api_key,
            },
            params={"q": query, "count": self.max_results},
        )
        resp.raise_for_status()
        items = resp.json().get("results", [])
        results = []
        for item in items:
            url = item.get("url", "")
            results.append({
                "id": _result_id(url),
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("description", ""),
                "source_domain": _domain(url),
                "date": item.get("age", ""),
            })
        return results

    def search_and_scrape(self, query: str) -> list[dict]:
        results = self.search(query)
        for r in results:
            if r.get("url"):
                r["full_text"] = _fetch_page_text(r["url"], self.max_chars)
        return results

    def close(self):
        self._http.close()


def get_searcher(config: dict):
    """Return the appropriate searcher based on config."""
    srch = config.get("search", {})
    if srch.get("backend") == "brave" and srch.get("brave_api_key"):
        return BraveSearcher(config)
    return DuckDuckGoSearcher(config)
