"""End-to-end pipeline test using mock email data (core/mock_email_client.py) in place
of the real Gmail API. Runs the full Layer 1-5 pipeline against the local Ollama instance
and prints the resulting brief without touching the production pipeline.db or outputs/.

Usage:
    python test_e2e.py --category software_ai
    python test_e2e.py --all-categories
"""
import argparse
import asyncio
import logging

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

from agents import aggregator, classifier, delivery, extractor
from core import mock_email_client
from core.database import Database
from core.llm_client import LLMClient

console = Console()


def setup_logging() -> None:
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def load_filters(path: str = "config/filters.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


async def run(category: str | None) -> None:
    setup_logging()
    load_dotenv()

    config = load_filters()
    filters = config["filters"]
    settings = config.get("settings", {})
    min_confidence = settings.get("min_confidence", 0.7)

    db = Database(db_path="/tmp/test_pipeline.db")
    await db.init()
    llm = LLMClient(db=db)
    console.rule("[bold]Newsletter Pipeline — End-to-End Test (mock Gmail)[/bold]")
    console.print(f"LLM provider: {llm.provider}  model: {llm.model}\n")

    emails = await mock_email_client.fetch_emails()
    console.print(f"[bold]Layer 1 (Ingestion):[/bold] loaded {len(emails)} mock emails\n")

    classified = await classifier.classify_emails(emails, filters, llm, db, min_confidence)
    console.print("[bold]Layer 2 (Classification):[/bold]")
    for c in classified:
        console.print(
            f"  [{'newsletter' if c.is_newsletter else 'skip'}] "
            f"{c.email.subject[:60]!r} -> category={c.category} "
            f"confidence={c.confidence:.2f}"
        )
    console.print()

    by_category: dict[str, list] = {}
    for c in classified:
        if c.is_newsletter and c.category != "none":
            by_category.setdefault(c.category, []).append(c)

    categories = [category] if category else [f["name"] for f in filters]

    for cat in categories:
        classified_list = by_category.get(cat, [])
        if not classified_list:
            console.print(f"[yellow]No newsletters matched category '{cat}', skipping.[/yellow]\n")
            continue

        console.rule(f"Category: {cat}")
        insights = await extractor.extract_all(classified_list, llm, db)
        console.print(f"[bold]Layer 3 (Extraction):[/bold] {len(insights)} atomic insights extracted\n")

        summary = await aggregator.aggregate_category(cat, insights, llm)
        if summary is None:
            console.print("[yellow]Aggregation returned no summary.[/yellow]\n")
            continue

        console.print("[bold]Layer 4+5 (Aggregation + Delivery):[/bold]\n")
        console.print(delivery.format_markdown(summary))
        console.print()


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end pipeline test with mock Gmail data")
    parser.add_argument("--category", help="Run a single category by name")
    parser.add_argument("--all-categories", action="store_true", help="Run all configured categories")
    args = parser.parse_args()
    asyncio.run(run(args.category))


if __name__ == "__main__":
    main()
