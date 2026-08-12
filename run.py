"""
Entry point — starts the scheduler and web dashboard together.

Usage:
  python run.py              # Normal start (scheduler + web server)
  python run.py --run-now   # Run the pipeline immediately, then start server
  python run.py --no-sched  # Web server only (no daily schedule)
"""
import asyncio
import sys
import os

import uvicorn

import config
from storage.db import init_db
from scheduler import create_scheduler, run_pipeline


async def main():
    run_now = "--run-now" in sys.argv
    no_sched = "--no-sched" in sys.argv

    init_db()

    if run_now:
        print("[run.py] Running pipeline now before starting server…")
        await run_pipeline()

    scheduler = None
    if not no_sched:
        scheduler = create_scheduler()
        scheduler.start()
        print(f"[run.py] Scheduler started — pipeline runs daily at {config.SCHEDULE_TIME} IST")

    server_config = uvicorn.Config(
        "web.app:app",
        host="0.0.0.0",
        port=config.WEB_PORT,
        log_level="info",
        reload=False,
    )
    server = uvicorn.Server(server_config)

    print(f"[run.py] Dashboard → http://localhost:{config.WEB_PORT}")

    try:
        await server.serve()
    finally:
        if scheduler:
            scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
