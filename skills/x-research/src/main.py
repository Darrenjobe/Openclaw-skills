#!/usr/bin/env python3
"""
x-research — CLI entry point

Examples
--------
Run a research pass with topics from config.yaml:
    python src/main.py run

Override topics for a single run:
    python src/main.py run --topic "raspberry pi" --topic "AI hardware"

Query stored results:
    python src/main.py recent --topic "AI news" --limit 10
    python src/main.py top --topic "AI news"
    python src/main.py hashtags

Use a custom config file:
    python src/main.py --config /path/to/config.yaml run
"""

import json
import logging
import sys
from pathlib import Path

import click
import yaml
from rich import box
from rich.console import Console
from rich.table import Table

# Allow running as `python src/main.py` from anywhere
SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT))              # skill root → enables `from src...`
sys.path.insert(0, str(SKILL_ROOT.parents[1]))   # repo root  → enables `from shared...`

from src.researcher import Researcher  # noqa: E402

console = Console()


# ── Config loader ─────────────────────────────────────────────────────────────


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        console.print(
            f"[bold red]Config file not found:[/] {config_path}\n"
            f"Copy [cyan]config.example.yaml[/] to [cyan]config.yaml[/] and fill in your settings.",
            highlight=False,
        )
        sys.exit(1)
    with config_path.open() as f:
        return yaml.safe_load(f) or {}


# ── CLI ───────────────────────────────────────────────────────────────────────


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config.yaml (defaults to skill root/config.yaml)",
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None) -> None:
    """x-research: track trends and news on X for specified topics."""
    ctx.ensure_object(dict)
    resolved = config_path or (SKILL_ROOT / "config.yaml")
    cfg = load_config(resolved)

    log_cfg = cfg.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_dir_str = log_cfg.get("log_dir")
    log_dir = (SKILL_ROOT / log_dir_str) if log_dir_str else None

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "x-research.log")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(fh)

    ctx.obj["config"] = cfg
    ctx.obj["skill_root"] = SKILL_ROOT


# ── run ───────────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--topic", "topics", multiple=True, help="Topic to research (repeatable). Overrides config.yaml.")
@click.option("--json-out", is_flag=True, default=False, help="Print the summary JSON to stdout.")
@click.pass_context
def run(ctx: click.Context, topics: tuple[str, ...], json_out: bool) -> None:
    """Fetch tweets for all configured topics and store results."""
    cfg = ctx.obj["config"]
    skill_root = ctx.obj["skill_root"]

    researcher = Researcher(cfg, skill_root)
    try:
        summary = researcher.run(topics=list(topics) if topics else None)
    finally:
        researcher.close()

    if json_out:
        console.print_json(json.dumps(summary))
    else:
        _print_run_summary(summary)


# ── recent ────────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--topic", default=None, help="Filter by topic.")
@click.option("--limit", default=20, show_default=True, help="Number of results.")
@click.pass_context
def recent(ctx: click.Context, topic: str | None, limit: int) -> None:
    """Show the most recently collected tweets from the database."""
    cfg = ctx.obj["config"]
    skill_root = ctx.obj["skill_root"]

    researcher = Researcher(cfg, skill_root)
    try:
        tweets = researcher.recent(topic=topic, limit=limit)
    finally:
        researcher.close()

    _print_tweets_table(tweets, title=f"Recent tweets{' — ' + topic if topic else ''}")


# ── top ───────────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--topic", default=None, help="Filter by topic.")
@click.option("--limit", default=10, show_default=True, help="Number of results.")
@click.pass_context
def top(ctx: click.Context, topic: str | None, limit: int) -> None:
    """Show top tweets ranked by engagement (retweets×2 + likes + replies)."""
    cfg = ctx.obj["config"]
    skill_root = ctx.obj["skill_root"]

    researcher = Researcher(cfg, skill_root)
    try:
        tweets = researcher.top(topic=topic, limit=limit)
    finally:
        researcher.close()

    _print_tweets_table(tweets, title=f"Top by engagement{' — ' + topic if topic else ''}")


# ── hashtags ─────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--topic", default=None, help="Filter by topic.")
@click.option("--limit", default=15, show_default=True, help="Number of hashtags.")
@click.pass_context
def hashtags(ctx: click.Context, topic: str | None, limit: int) -> None:
    """Show the most frequent hashtags across stored tweets."""
    cfg = ctx.obj["config"]
    skill_root = ctx.obj["skill_root"]

    researcher = Researcher(cfg, skill_root)
    try:
        tags = researcher.trending_hashtags(topic=topic, limit=limit)
    finally:
        researcher.close()

    table = Table(title=f"Trending hashtags{' — ' + topic if topic else ''}", box=box.SIMPLE_HEAVY)
    table.add_column("Rank", style="dim", width=6)
    table.add_column("Hashtag", style="bold cyan")
    table.add_column("Count", justify="right")

    for rank, (tag, count) in enumerate(tags, 1):
        table.add_row(str(rank), f"#{tag}", str(count))

    console.print(table)


# ── Rich helpers ──────────────────────────────────────────────────────────────


def _print_run_summary(summary: dict) -> None:
    run_info = summary.get("run", {})
    console.rule("[bold green]Research run complete")
    console.print(
        f"  Source     : [cyan]{run_info.get('source')}[/]\n"
        f"  Started    : {run_info.get('started_at')}\n"
        f"  Finished   : {run_info.get('finished_at')}\n"
        f"  New stored : [bold]{run_info.get('new_tweets_stored', 0)}[/] tweets\n"
    )

    for topic, data in summary.get("topics", {}).items():
        console.rule(f"[bold]{topic}")
        console.print(f"  Fetched: [bold]{data['tweet_count']}[/] tweets\n")

        if data["trending_hashtags"]:
            tags = "  ".join(f"[cyan]#{h['tag']}[/]({h['count']})" for h in data["trending_hashtags"][:8])
            console.print(f"  Trending: {tags}\n")

        for i, t in enumerate(data["top_tweets"], 1):
            console.print(
                f"  [dim]{i}.[/] [bold]@{t['author']}[/]  "
                f"[green]♥{t['likes']}[/] [yellow]↺{t['retweets']}[/] [blue]💬{t['replies']}[/]\n"
                f"     {t['content'][:120]}…\n"
                f"     [link={t['url']}]{t['url']}[/link]\n"
            )


def _print_tweets_table(tweets: list[dict], title: str) -> None:
    if not tweets:
        console.print("[yellow]No tweets found.[/]")
        return

    table = Table(title=title, box=box.SIMPLE_HEAVY, show_lines=True)
    table.add_column("Author", style="bold cyan", width=18)
    table.add_column("Content", width=60)
    table.add_column("♥", justify="right", width=7)
    table.add_column("↺", justify="right", width=7)
    table.add_column("Topic", style="dim", width=16)

    for t in tweets:
        content = t.get("content", "")
        content_short = content[:120] + ("…" if len(content) > 120 else "")
        table.add_row(
            f"@{t.get('author', '')}",
            content_short,
            str(t.get("likes", 0)),
            str(t.get("retweets", 0)),
            t.get("topic", ""),
        )

    console.print(table)


# ── Entry point ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    cli()
