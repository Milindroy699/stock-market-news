"""Fetches top posts from r/IndiaInvestments using Reddit's public JSON API."""
import hashlib
from datetime import datetime
import httpx
import config


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# Using Reddit's Atom RSS feed — works without auth or API keys
REDDIT_RSS_URL = "https://www.reddit.com/r/IndiaInvestments/top/.rss?t=day&limit=10"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


async def fetch(max_items: int = 5) -> list[dict]:
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "application/atom+xml, application/xml, text/xml, */*",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(REDDIT_RSS_URL, headers=headers)
            resp.raise_for_status()
            raw = resp.text
    except Exception as e:
        print(f"[RedditIndiaInvestments] fetch failed — {e}")
        return []

    import feedparser
    feed = feedparser.parse(raw)
    articles = []
    for entry in feed.entries[:max_items]:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "")
        content = getattr(entry, "summary", "")[:1500]

        # Strip HTML tags from content
        import re
        content = re.sub(r"<[^>]+>", " ", content).strip()

        pub = getattr(entry, "published_parsed", None)
        pub_date = datetime(*pub[:6]) if pub else datetime.utcnow()

        if title:
            articles.append({
                "source": "r/IndiaInvestments",
                "category": "community",
                "title": title,
                "url": link,
                "url_hash": _hash(link),
                "content": content,
                "published_at": pub_date,
            })

    return articles
