"""
Claude API integration for summarizing web research results.

Sends scraped article content to Claude and returns a structured
summary with per-source breakdowns and an overall synthesis.
"""

import os

import anthropic

from shared.utils import setup_logging

logger = setup_logging("web-research.summarizer")

_PROMPT_TEMPLATE = """\
You are a research assistant. The user asked: "{query}"

Below are {n} articles retrieved from the web. For each article:
- Write a 2-3 sentence summary of its key claims or findings.
- Note the source domain and date if available.

Then write an OVERALL SUMMARY (4-6 sentences) that synthesizes the most important \
findings across all sources.

Format your response EXACTLY as follows:

OVERALL SUMMARY:
<your synthesis here>

SOURCES:
1. [{title}] ({domain}) — <2-3 sentence summary>
2. ...

---
ARTICLES:
{articles}
"""


class Summarizer:
    def __init__(self, config: dict):
        api_key = (
            config.get("claude", {}).get("api_key")
            or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        if not api_key:
            raise ValueError(
                "Claude API key not found. Set claude.api_key in config.yaml "
                "or export ANTHROPIC_API_KEY=your_key"
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = config.get("claude", {}).get("model", "claude-haiku-4-5-20251001")
        self.max_tokens = config.get("claude", {}).get("max_tokens", 1500)

    def summarize(self, query: str, results: list[dict]) -> str:
        """
        Send search results to Claude and return a structured summary string.

        Args:
            query:   The original search query / research question.
            results: List of result dicts with title, url, snippet, full_text, etc.

        Returns:
            Structured text with overall summary + per-source summaries.
        """
        article_blocks = []
        for i, r in enumerate(results, 1):
            parts = [
                f"Article {i}: {r.get('title', 'Untitled')}",
                f"Source: {r.get('source_domain', '')} | URL: {r.get('url', '')}",
            ]
            if r.get("date"):
                parts.append(f"Date: {r['date']}")
            content = r.get("full_text") or r.get("snippet", "")
            if content:
                # Limit per-article context to keep prompt size manageable
                parts.append(f"Content:\n{content[:3000]}")
            article_blocks.append("\n".join(parts))

        prompt = _PROMPT_TEMPLATE.format(
            query=query,
            n=len(results),
            title="Title",
            domain="Domain",
            articles="\n\n---\n\n".join(article_blocks),
        )

        logger.info(
            "Sending %d articles to Claude (%s) for '%s'",
            len(results), self.model, query,
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
