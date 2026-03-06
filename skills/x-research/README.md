# x-research

Research X (Twitter) for **trends and latest news** on any topic and store results locally in SQLite.

## Features

- **Dual backends** — X API v2 (with Bearer Token) or Nitter scraping (no credentials needed)
- **SQLite storage** — lightweight, no external database, perfect for Raspberry Pi
- **JSON exports** — human-readable summary per run saved to `data/exports/`
- **Trend detection** — top tweets by engagement, trending hashtags
- **CLI** — run manually or from cron
- **Configurable** — topics, max results, retention period, log level

## Setup

### 1. Install dependencies

```bash
cd skills/x-research
pip install -r requirements.txt
```

### 2. Create your config

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` — at minimum, add your topics:

```yaml
topics:
  - "raspberry pi"
  - "AI news"
```

### 3. (Optional) Add an X API v2 Bearer Token

For higher quality results, get a free Bearer Token at <https://developer.twitter.com/> and add it to `config.yaml`:

```yaml
x_api:
  bearer_token: "AAAA..."
```

Without a token the skill falls back to Nitter scraping (public instances, no auth required).

## Usage

```bash
# Run a research pass with topics from config.yaml
python src/main.py run

# Research specific topics (overrides config.yaml for this run)
python src/main.py run --topic "raspberry pi" --topic "AI hardware"

# Print the run summary as JSON
python src/main.py run --json-out

# Query stored results
python src/main.py recent                        # most recent tweets across all topics
python src/main.py recent --topic "AI news"     # filter by topic
python src/main.py top --topic "AI news"        # top by engagement
python src/main.py hashtags                     # trending hashtags across all topics
python src/main.py hashtags --topic "AI news"

# Use a custom config file
python src/main.py --config /etc/openclaw/x-research.yaml run
```

## Scheduled Runs (cron)

Add to crontab to run every 6 hours:

```cron
0 */6 * * * cd /path/to/Openclaw-skills/skills/x-research && /usr/bin/python3 src/main.py run >> data/logs/cron.log 2>&1
```

## Data Layout

```
data/
├── x_research.db      # SQLite — all stored tweets and run logs
├── exports/           # JSON summary for each run, timestamped
│   └── 2025-06-10T14-00-00Z.json
└── logs/
    └── x-research.log
```

The `data/` directory is gitignored and created automatically on first run.

## Config Reference

| Key | Default | Description |
|-----|---------|-------------|
| `topics` | `[]` | List of search topics |
| `x_api.bearer_token` | `""` | X API v2 Bearer Token (optional) |
| `x_api.max_results` | `20` | Tweets per topic (10–100) |
| `nitter.instances` | (list) | Nitter instances to try in order |
| `nitter.max_results` | `20` | Tweets to scrape per topic |
| `storage.db_path` | `data/x_research.db` | SQLite path |
| `storage.export_json` | `true` | Write JSON summary each run |
| `storage.keep_days` | `30` | Purge tweets older than N days |
| `logging.level` | `INFO` | Log level |

## Running Tests

```bash
# From the repo root
pytest skills/x-research/tests/ -v
```
