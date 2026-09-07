import argparse
import asyncio
import logging
import os

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

from agents import aggregator, classifier, delivery, extractor, ingestion
from core.database import Database
from core.email_client import run_auth_flow
from core.llm_client import LLMClient

console = Console()


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def load_filters(path: str = "config/filters.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


async def run(args: argparse.Namespace) -> None:
    setup_logging()
    load_dotenv()

    config = load_filters()
    filters = config["filters"]
    settings = config.get("settings", {})
    hours_back = args.hours_back or settings.get("hours_back", 24)
    min_confidence = settings.get("min_confidence", 0.7)
    output_dir = settings.get("output_dir", "outputs/")

    db = Database()
    await db.init()
    llm = LLMClient(db=db)

    emails = await ingestion.fetch_emails(hours_back=hours_back)
    classified = await classifier.classify_emails(
        emails, filters, llm, db, min_confidence
    )

    classified_by_category: dict[str, list] = {}
    for c in classified:
        if c.is_newsletter and c.category != "none":
            classified_by_category.setdefault(c.category, []).append(c)

    if args.category:
        categories = [args.category]
    else:
        categories = [f["name"] for f in filters]

    summaries = []
    for category_name in categories:
        classified_list = classified_by_category.get(category_name, [])
        if not classified_list:
            logging.info("No newsletters matched category '%s'", category_name)
            continue
        insights = await extractor.extract_all(classified_list, llm, db)
        summary = await aggregator.aggregate_category(category_name, insights, llm)
        if summary:
            summaries.append(summary)

    if args.dry_run:
        for summary in summaries:
            console.print(delivery.format_markdown(summary))
    elif summaries:
        from datetime import datetime, timezone

        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        delivery.deliver(summaries, date, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Newsletter Intelligence Pipeline")
    parser.add_argument("--category", help="Run a single category by name")
    parser.add_argument(
        "--all-categories", action="store_true", help="Run all configured categories"
    )
    parser.add_argument(
        "--hours-back", type=int, default=None, help="Override hours_back window"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print output without writing files"
    )
    parser.add_argument(
        "--auth", action="store_true", help="Run Gmail OAuth flow and exit"
    )
    args = parser.parse_args()

    if args.auth:
        run_auth_flow()
        return

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
