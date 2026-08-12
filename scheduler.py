"""APScheduler job that runs the full pipeline daily at a configured time (IST)."""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime
import pytz
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from storage.db import get_session, PipelineRun, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("scheduler")

IST = pytz.timezone("Asia/Kolkata")


async def run_pipeline():
    """Execute all pipeline stages sequentially and record the run in DB."""
    init_db()
    today = date.today()
    started = datetime.utcnow()
    log.info(f"=== Pipeline starting for {today} ===")

    articles_fetched = 0
    transcripts_fetched = 0
    error_msg = None

    try:
        # 1. Fetch news
        from agents.news_aggregator import run as agg_run
        articles_fetched = await agg_run()

        # 2. Fetch YouTube transcripts (non-blocking — runs in thread pool)
        from agents.youtube_fetcher import run as yt_run
        transcripts_fetched = await asyncio.get_event_loop().run_in_executor(None, yt_run)

        # 3. Market data + TA
        from agents.market_data import run as md_run
        market_result = await asyncio.get_event_loop().run_in_executor(None, md_run)

        from agents.technical_analyst import run_for_all
        await asyncio.get_event_loop().run_in_executor(None, run_for_all)

        # 4. AI summarisation
        from agents.summarizer import run as sum_run
        await asyncio.get_event_loop().run_in_executor(None, sum_run)

        # 5. AI recommendations
        from agents.recommender import run as rec_run
        await asyncio.get_event_loop().run_in_executor(None, rec_run)

        log.info(f"=== Pipeline complete: {articles_fetched} articles, {transcripts_fetched} transcripts ===")

    except Exception as e:
        error_msg = str(e)
        log.error(f"Pipeline error: {e}", exc_info=True)

    # Record run
    with get_session() as session:
        session.add(PipelineRun(
            run_date=today,
            started_at=started,
            completed_at=datetime.utcnow(),
            success=error_msg is None,
            error_message=error_msg,
            articles_fetched=articles_fetched,
            transcripts_fetched=transcripts_fetched,
        ))
        session.commit()


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)

    hour, minute = config.SCHEDULE_TIME.split(":")
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(hour=int(hour), minute=int(minute), timezone=IST),
        id="daily_pipeline",
        name="Daily Market Digest Pipeline",
        misfire_grace_time=3600,
        replace_existing=True,
    )
    log.info(f"Scheduler configured: daily at {config.SCHEDULE_TIME} IST")
    return scheduler


if __name__ == "__main__":
    # Run once immediately (useful for testing)
    asyncio.run(run_pipeline())
