import argparse
import asyncio
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from main import run, setup_logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _run_all_categories() -> None:
    args = argparse.Namespace(
        category=None, all_categories=True, hours_back=None, dry_run=False, auth=False
    )
    asyncio.run(run(args))


def main() -> None:
    setup_logging()
    load_dotenv()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        _run_all_categories,
        trigger=CronTrigger(hour=7, minute=0),
        id="daily_newsletter_digest",
        name="Daily newsletter digest",
    )
    logger.info("Scheduler started. Daily job set for 7:00 AM local time.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
