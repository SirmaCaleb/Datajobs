"""
Scheduler — runs all scrapers every N hours using APScheduler.

Usage:
  python scheduler.py             # start scheduler daemon
  python scheduler.py --run-now  # run once immediately and exit
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import settings, SEARCH_TERMS
from scrapers import ALL_SCRAPERS

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("scheduler")
console = Console(highlight=False)
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def run_all_scrapers():
    """Instantiate and run every scraper. Prints a summary table."""
    console.rule(f"[bold]Scrape run — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    results: list[dict] = []

    for ScraperClass in ALL_SCRAPERS:
        name = ScraperClass.source_name
        console.print(f"[cyan]→[/cyan] Starting [bold]{name}[/bold]")
        try:
            scraper = ScraperClass()
            new_count = scraper.run(search_terms=SEARCH_TERMS)
            results.append({"source": name, "new": new_count, "status": "✓"})
        except Exception as e:
            logger.error(f"{name} crashed: {e}", exc_info=True)
            results.append({"source": name, "new": 0, "status": "✗ " + str(e)[:40]})

    # Summary table
    table = Table(title="Scrape Summary", show_header=True, header_style="bold magenta")
    table.add_column("Source", style="cyan")
    table.add_column("New Jobs", justify="right")
    table.add_column("Status")

    total_new = 0
    for r in results:
        table.add_row(r["source"], str(r["new"]), r["status"])
        total_new += r["new"]

    table.add_section()
    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total_new}[/bold]", "")

    console.print(table)
    console.print(f"[green]Done.[/green] Next run in {settings.scrape_interval_hours}h\n")


def main():
    parser = argparse.ArgumentParser(description="DataJobs scraper scheduler")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run all scrapers once immediately and exit",
    )
    args = parser.parse_args()

    if args.run_now:
        run_all_scrapers()
        sys.exit(0)

    # Start the scheduler
    console.print(
        f"[bold green]DataJobs Scheduler[/bold green] starting — "
        f"interval: every [bold]{settings.scrape_interval_hours}h[/bold]"
    )

    # Run immediately on start
    run_all_scrapers()

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_all_scrapers,
        trigger=IntervalTrigger(hours=settings.scrape_interval_hours),
        id="scrape_all",
        name="Scrape all sources",
        misfire_grace_time=300,
    )

    console.print("[dim]Scheduler running. Press Ctrl+C to stop.[/dim]\n")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("[yellow]Scheduler stopped.[/yellow]")


if __name__ == "__main__":
    main()
