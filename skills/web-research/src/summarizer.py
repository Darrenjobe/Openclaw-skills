"""
AI summarization backends for web-research.

Supports two providers:
  - claude  — Anthropic Claude API (default)
  - grok    — xAI Grok API (OpenAI-compatible endpoint)

Configure in config.yaml under the `ai:` section, e.g.:

    ai:
      provider: grok          # or "claude"
      grok:
        api_key: ""           # or export XAI_API_KEY
        model: "grok-2-latest"

Use get_summarizer(config) to obtain the right backend automatically.
"""

import os
from abc import ABC, abstractmethod

from shared.utils import setup_logging

logger = setup_logging("web-research.summarizer")

# ── Shared prompt ──────────────────────────────────────────────────────────────

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


def _build_prompt(query: str, results: list[dict]) -> str:
    """Render the shared research prompt from a query and result list."""
    blocks = []
    for i, r in enumerate(results, 1):
        parts = [
            f"Article {i}: {r.get('title', 'Untitled')}",
            f"Source: {r.get('source_domain', '')} | URL: {r.get('url', '')}",
        ]
        if r.get("date"):
            parts.append(f"Date: {r['date']}")
        content = r.get("full_text") or r.get("snippet", "")
        if content:
            parts.append(f"Content:\n{content[:3000]}")
        blocks.append("\n".join(parts))

    return _PROMPT_TEMPLATE.format(
        query=query,
        n=len(results),
        title="Title",
        domain="Domain",
        articles="\n\n---\n\n".join(blocks),
    )


# ── Abstract base ──────────────────────────────────────────────────────────────

class BaseSummarizer(ABC):
    @abstractmethod
    def summarize(self, query: str, results: list[dict]) -> str:
        """Return a structured summary string for the given query and results."""


# ── Claude backend ─────────────────────────────────────────────────────────────

class ClaudeSummarizer(BaseSummarizer):
    """
    Summarize using the Anthropic Claude API.

    Config keys (under ai.claude OR legacy top-level claude):
      api_key   — Anthropic API key (or set ANTHROPIC_API_KEY env var)
      model     — e.g. "claude-haiku-4-5-20251001" or "claude-sonnet-4-6"
      max_tokens — max tokens in the response (default 1500)
    """

    def __init__(self, cfg: dict):
        import anthropic

        api_key = (cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
        if not api_key:
            raise ValueError(
                "Claude API key not found. Set ai.claude.api_key in config.yaml "
                "or export ANTHROPIC_API_KEY=your_key"
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = cfg.get("model", "claude-haiku-4-5-20251001")
        self.max_tokens = cfg.get("max_tokens", 1500)

    def summarize(self, query: str, results: list[dict]) -> str:
        prompt = _build_prompt(query, results)
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


# ── Grok backend ───────────────────────────────────────────────────────────────

class GrokSummarizer(BaseSummarizer):
    """
    Summarize using xAI's Grok API (https://console.x.ai/).

    Calls https://api.x.ai/v1/chat/completions directly via httpx —
    no extra SDK required, works headlessly on Raspberry Pi.

    Config keys (under ai.grok):
      api_key    — xAI API key (or set XAI_API_KEY env var)
      model      — e.g. "grok-2-latest" or "grok-beta"
      max_tokens — max tokens in the response (default 1500)
    """

    _ENDPOINT = "https://api.x.ai/v1/chat/completions"

    def __init__(self, cfg: dict):
        import httpx

        api_key = (cfg.get("api_key") or os.environ.get("XAI_API_KEY", "")).strip()
        if not api_key:
            raise ValueError(
                "xAI API key not found. Set ai.grok.api_key in config.yaml "
                "or export XAI_API_KEY=your_key  "
                "(get one at https://console.x.ai/)"
            )
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.model = cfg.get("model", "grok-2-latest")
        self.max_tokens = cfg.get("max_tokens", 1500)
        self._http = httpx.Client(timeout=60)

    def summarize(self, query: str, results: list[dict]) -> str:
        prompt = _build_prompt(query, results)
        logger.info(
            "Sending %d articles to Grok (%s) for '%s'",
            len(results), self.model, query,
        )
        resp = self._http.post(
            self._ENDPOINT,
            headers=self._headers,
            json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def close(self):
        self._http.close()


# ── Factory ────────────────────────────────────────────────────────────────────

def get_summarizer(config: dict) -> BaseSummarizer:
    """
    Return the correct summarizer based on config.

    Resolution order:
      1. ai.provider key (new-style)
      2. Backwards-compatible: if top-level `claude:` key exists, use Claude
      3. Default to Claude
    """
    ai_cfg = config.get("ai", {})
    provider = ai_cfg.get("provider", "").lower()

    # Backwards-compat: old config had a top-level `claude:` section
    if not provider:
        provider = "claude"

    if provider == "grok":
        grok_cfg = ai_cfg.get("grok", {})
        return GrokSummarizer(grok_cfg)

    if provider == "claude":
        # New-style: ai.claude section; fallback to legacy top-level claude section
        claude_cfg = ai_cfg.get("claude") or config.get("claude", {})
        return ClaudeSummarizer(claude_cfg)

    raise ValueError(
        f"Unknown AI provider '{provider}'. "
        "Valid options: 'claude', 'grok'."
    )
