"""Fetches articles from all configured sources and stores new ones in the DB."""
import asyncio
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from sources.rss_base import fetch_rss
from sources.the_ken import fetch as fetch_the_ken
from sources.zerodha_daily_brief import fetch as fetch_daily_brief
from sources.nse_announcements import fetch as fetch_nse
from sources.capitalmind_podcasts import fetch as fetch_capitalmind_pods
from sources.varsity import fetch as fetch_varsity
from sources.reddit_india import fetch as fetch_reddit
from sources.moneycontrol import fetch as fetch_moneycontrol
from storage.db import get_session, Article, init_db


def _save_articles(articles: list[dict]) -> int:
    """Insert new articles, skip duplicates. Returns count of new rows."""
    saved = 0
    with get_session() as session:
        for a in articles:
            exists = session.query(Article).filter_by(url_hash=a["url_hash"]).first()
            if exists:
                continue
            row = Article(
                source=a["source"],
                category=a.get("category"),
                title=a["title"],
                url=a.get("url"),
                url_hash=a["url_hash"],
                content=a.get("content"),
                published_at=a.get("published_at"),
                fetch_date=date.today(),
            )
            session.add(row)
            saved += 1
        session.commit()
    return saved


async def run() -> int:
    """Fetch all sources in parallel and persist new articles. Returns total saved."""
    init_db()
    tasks = []

    # The Ken — uses curl_cffi with Chrome TLS impersonation to bypass Cloudflare
    tasks.append(fetch_the_ken(config.MAX_ARTICLES_PER_SOURCE))

    # All other RSS sources (The Ken is handled above)
    for src in config.RSS_SOURCES:
        if src["name"] == "The Ken":
            continue
        tasks.append(fetch_rss(src["name"], src["url"], src["category"], config.MAX_ARTICLES_PER_SOURCE))

    # Scrape sources
    tasks.append(fetch_daily_brief())
    tasks.append(fetch_nse())
    tasks.append(fetch_capitalmind_pods())
    tasks.append(fetch_varsity())
    tasks.append(fetch_reddit())
    # Moneycontrol blocks non-browser traffic; skip unless a proxy/cookie solution is added
    # tasks.append(fetch_moneycontrol())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: list[dict] = []
    for r in results:
        if isinstance(r, Exception):
            print(f"[Aggregator] source error: {r}")
        elif isinstance(r, list):
            all_articles.extend(r)

    total_saved = _save_articles(all_articles)
    print(f"[Aggregator] Fetched {len(all_articles)} articles, saved {total_saved} new")
    return total_saved


def get_today_articles(limit: int = None) -> list[Article]:
    with get_session() as session:
        q = session.query(Article).filter(Article.fetch_date == date.today()).order_by(Article.fetched_at.desc())
        if limit:
            q = q.limit(limit)
        return q.all()


if __name__ == "__main__":
    asyncio.run(run())
