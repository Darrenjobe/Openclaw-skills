# web-research

Search the web, scrape articles, and get an AI-generated summary — entirely headlessly on your Raspberry Pi. No browser, no display required.

## How it works

```
1. DuckDuckGo (free, no API key)  ──▶  list of URLs + snippets
2. trafilatura (HTTP-based)        ──▶  clean article text per URL
3. Claude API (Haiku by default)   ──▶  overall summary + per-source summaries
4. SQLite                          ──▶  stored locally for later review
```

## Quick Start

```bash
cd skills/web-research
make setup
# Edit config.yaml and set your Anthropic API key (or export ANTHROPIC_API_KEY=...)
make ask Q="What is the latest news in Iran?"
```

## Setup

```bash
make setup
```

This creates:
- `.venv/` — isolated Python environment with all dependencies
- `config.yaml` — copy of `config.example.yaml` for you to edit

**Set your Anthropic API key** (one of two ways):

```bash
# Option A — in config.yaml
claude:
  api_key: "sk-ant-..."

# Option B — environment variable (recommended for Pi)
export ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at https://console.anthropic.com/

## Usage

### One-off research query

```bash
make ask Q="What is happening in Iran?"
make ask Q="Latest Raspberry Pi 5 news"
make ask Q="OpenAI vs Anthropic 2025"
```

Or directly:

```bash
.venv/bin/python src/main.py ask "Iran news"
```

### Scheduled research (from config.yaml queries)

```bash
make run
```

### View stored results

```bash
make recent
```

### JSON output (for scripting)

```bash
.venv/bin/python src/main.py ask "Iran news" --json-out | jq .
```

## Example Output

```
────────────────────── Iran latest news ──────────────────────
╭─ AI Summary ────────────────────────────────────────────────╮
│ OVERALL SUMMARY:                                            │
│ Recent reports indicate that Iran's ... [4-6 sentences]    │
│                                                             │
│ SOURCES:                                                    │
│ 1. [BBC News] (bbc.com) — Iran's parliament passed...      │
│ 2. [Reuters] (reuters.com) — Tensions along the...         │
╰─────────────────────────────────────────────────────────────╯
 #  Source       Title                         Date        URL
 1  bbc.com      Iran parliament passes...     2025-03-05  https://...
 2  reuters.com  Iran-US talks stall over...   2025-03-04  https://...
```

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `queries` | `[]` | List of queries for `make run` |
| `search.backend` | `duckduckgo` | `duckduckgo` (free) or `brave` (API key required) |
| `search.max_results` | `8` | Results fetched per query |
| `search.news_mode` | `true` | Search news articles vs general web |
| `scraping.max_content_chars` | `8000` | Max chars extracted per page |
| `claude.model` | `claude-haiku-4-5-20251001` | Haiku = fast + cheap; Sonnet = better quality |
| `claude.max_tokens` | `1500` | Max tokens in the summary |
| `storage.keep_days` | `30` | Auto-purge records older than N days |

## Scheduled Runs (cron)

```bash
crontab -e
```

Add:

```cron
0 */12 * * * cd /path/to/Openclaw-skills/skills/web-research && make run >> data/logs/cron.log 2>&1
```

## Data Layout

```
data/
├── web_research.db     # SQLite — all stored results
├── exports/            # JSON export per run (if enabled)
│   └── web_research_20250305_120000.json
└── logs/
    └── web-research.log
```

## Search Backends

### DuckDuckGo (default — no setup needed)

Uses the `duckduckgo-search` library. Free, no API key, no rate limit concerns for personal use.

### Brave Search API (optional upgrade)

Free tier: 2000 queries/month. Better news freshness than DDG for some topics.

```yaml
search:
  backend: "brave"
  brave_api_key: "BSA..."
```

Get a key at https://brave.com/search/api/

## Running Tests

```bash
make test
```
