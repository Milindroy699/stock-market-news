"""FastAPI web dashboard for the Stock Market News agent."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import date, timedelta
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from storage.db import get_session, DailyDigest, MarketSnapshot, Recommendation, PipelineRun, init_db

app = FastAPI(title="Market Digest", docs_url=None, redoc_url=None)

_BASE = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(_BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))

_pipeline_running = False


def _get_digest(target_date: date) -> DailyDigest | None:
    with get_session() as session:
        return session.query(DailyDigest).filter_by(digest_date=target_date).first()


def _get_snapshot(target_date: date) -> MarketSnapshot | None:
    with get_session() as session:
        return session.query(MarketSnapshot).filter_by(snapshot_date=target_date).first()


def _get_recommendations(target_date: date) -> tuple[list, list]:
    with get_session() as session:
        swing = session.query(Recommendation).filter_by(rec_date=target_date, rec_type="swing").all()
        longterm = session.query(Recommendation).filter_by(rec_date=target_date, rec_type="longterm").all()
        return swing, longterm


def _get_last_run() -> PipelineRun | None:
    with get_session() as session:
        return session.query(PipelineRun).order_by(PipelineRun.id.desc()).first()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, d: str = None):
    target = date.fromisoformat(d) if d else date.today()
    digest = _get_digest(target)
    snapshot = _get_snapshot(target)
    swing, longterm = _get_recommendations(target)
    last_run = _get_last_run()

    # Navigation dates
    prev_date = target - timedelta(days=1)
    next_date = target + timedelta(days=1)
    is_today = target == date.today()

    sector_icons = {
        "bullish": "🟢",
        "bearish": "🔴",
        "neutral": "🟡",
    }

    return templates.TemplateResponse(request, "dashboard.html", {
        "target_date": target,
        "prev_date": prev_date,
        "next_date": next_date,
        "is_today": is_today,
        "digest": digest,
        "snapshot": snapshot,
        "swing_picks": swing,
        "longterm_radar": longterm,
        "last_run": last_run,
        "sector_icons": sector_icons,
        "pipeline_running": _pipeline_running,
    })


@app.get("/picks", response_class=HTMLResponse)
async def picks_page(request: Request):
    swing, longterm = _get_recommendations(date.today())
    return templates.TemplateResponse(request, "watchlist.html", {
        "swing_picks": swing,
        "longterm_radar": longterm,
        "today": date.today(),
    })


@app.get("/run-now")
async def run_now(background_tasks: BackgroundTasks):
    global _pipeline_running
    if _pipeline_running:
        return JSONResponse({"status": "already_running"})
    _pipeline_running = True
    background_tasks.add_task(_run_pipeline)
    return JSONResponse({"status": "started"})


async def _run_pipeline():
    global _pipeline_running
    try:
        import importlib
        for mod_name in [
            "agents.news_aggregator",
            "agents.youtube_fetcher",
            "agents.market_data",
            "agents.technical_analyst",
            "agents.summarizer",
            "agents.recommender",
        ]:
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, "run", None) or getattr(mod, "run_for_all", None)
            if fn:
                if asyncio.iscoroutinefunction(fn):
                    await fn()
                else:
                    await asyncio.get_event_loop().run_in_executor(None, fn)
    except Exception as e:
        print(f"[Pipeline] Error: {e}")
    finally:
        _pipeline_running = False


@app.get("/health")
async def health():
    last_run = _get_last_run()
    return JSONResponse({
        "status": "ok",
        "pipeline_running": _pipeline_running,
        "last_run": {
            "date": str(last_run.run_date) if last_run else None,
            "success": last_run.success if last_run else None,
            "articles_fetched": last_run.articles_fetched if last_run else 0,
        }
    })
