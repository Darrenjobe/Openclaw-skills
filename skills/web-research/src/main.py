#!/usr/bin/env python3
"""Web Research Skill — CLI entry point."""

import json
import sys
from pathlib import Path

# Allow running from any working directory
_SKILL_ROOT = Path(__file__).parent.parent
_REPO_ROOT = _SKILL_ROOT.parent.parent
sys.path.insert(0, str(_REPO_ROOT))   # exposes shared/
sys.path.insert(0, str(_SKILL_ROOT))  # exposes src/

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from src.researcher import WebResearcher
from shared.utils import setup_logging

console = Console()


def _load_config() -> dict:
    config_path = _SKILL_ROOT / "config.yaml"
    if not config_path.exists():
        console.print(
            "[red]config.yaml not found.[/red] Run [bold]make setup[/bold] first."
        )
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


@click.group()
def cli():
    """Web Research Skill — search the web, scrape pages, get AI summaries."""


@cli.command()
@click.option("--query", "-q", multiple=True, help="Override configured queries.")
@click.option("--json-out", is_flag=True, help="Print summary JSON to stdout.")
def run(query, json_out):
    """Run a research pass on all configured queries."""
    config = _load_config()
    log_dir = _SKILL_ROOT / config.get("logging", {}).get("log_dir", "data/logs")
    logger = setup_logging("web-research", log_dir)

    queries = list(query) or config.get("queries", [])
    if not queries:
        console.print(
            "[red]No queries configured.[/red] "
            "Add queries to config.yaml or use [bold]--query[/bold]."
        )
        sys.exit(1)

    researcher = WebResearcher(config, _SKILL_ROOT, logger)
    try:
        summary = researcher.run(queries)
        if json_out:
            console.print(json.dumps(summary, indent=2))
        else:
            _print_run_summary(summary)
    finally:
        researcher.close()


@cli.command()
@click.argument("query_text")
@click.option("--json-out", is_flag=True, help="Print summary JSON to stdout.")
def ask(query_text, json_out):
    """Run a one-off research query and display results immediately.

    Example: python src/main.py ask "What is happening in Iran?"
    """
    config = _load_config()
    log_dir = _SKILL_ROOT / config.get("logging", {}).get("log_dir", "data/logs")
    logger = setup_logging("web-research", log_dir)

    researcher = WebResearcher(config, _SKILL_ROOT, logger)
    try:
        summary = researcher.run([query_text])
        if json_out:
            console.print(json.dumps(summary, indent=2))
        else:
            _print_run_summary(summary)
    finally:
        researcher.close()


@cli.command()
@click.option("--query", "-q", default=None, help="Filter by query.")
@click.option("--limit", "-n", default=20, show_default=True, help="Number of results.")
def recent(query, limit):
    """Show most recently stored research results."""
    config = _load_config()
    logger = setup_logging("web-research")
    researcher = WebResearcher(config, _SKILL_ROOT, logger)
    try:
        results = researcher.recent(query=query, limit=limit)
        _print_results_table(results)
    finally:
        researcher.close()


# ── Display helpers ────────────────────────────────────────────────────────────

def _print_run_summary(summary: dict):
    for query, data in summary.get("queries", {}).items():
        console.rule(f"[bold cyan]{query}[/bold cyan]")

        overall = data.get("overall_summary", "")
        if overall:
            console.print(Panel(overall, title="[bold]AI Summary[/bold]", border_style="green"))

        results = data.get("results", [])
        if results:
            table = Table(show_header=True, header_style="bold magenta", expand=True)
            table.add_column("#", style="dim", width=3)
            table.add_column("Source", style="cyan", max_width=22)
            table.add_column("Title", style="white")
            table.add_column("Date", style="dim", max_width=12)
            table.add_column("URL", style="blue")

            for i, r in enumerate(results, 1):
                table.add_row(
                    str(i),
                    r.get("source_domain", ""),
                    r.get("title", "")[:70],
                    (r.get("date") or "")[:10],
                    r.get("url", ""),
                )
            console.print(table)


def _print_results_table(results: list):
    if not results:
        console.print("[dim]No results stored yet.[/dim]")
        return
    table = Table(
        title="Stored Research Results",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )
    table.add_column("Query", style="cyan", max_width=25)
    table.add_column("Title", style="white")
    table.add_column("Source", style="green", max_width=20)
    table.add_column("Collected", style="dim", max_width=16)

    for r in results:
        table.add_row(
            r.get("query", ""),
            r.get("title", "")[:65],
            r.get("source_domain", ""),
            (r.get("collected_at") or "")[:16],
        )
    console.print(table)


if __name__ == "__main__":
    cli()
