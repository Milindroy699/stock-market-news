"""Shared RSS fetching utility used by all RSS-based sources."""
import hashlib
from datetime import datetime
from email.utils import parsedate_to_datetime
import feedparser
import httpx


def _hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6])
            except Exception:
                pass
    return None


async def fetch_rss(name: str, url: str, category: str, max_items: int = 5, cookies: dict | None = None) -> list[dict]:
    """Return a list of article dicts from an RSS feed URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, cookies=cookies or {}) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            raw = resp.text
    except Exception as e:
        print(f"[RSS] {name}: fetch failed — {e}")
        return []

    feed = feedparser.parse(raw)
    articles = []
    for entry in feed.entries[:max_items]:
        article_url = getattr(entry, "link", "") or ""
        content = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        )
        articles.append({
            "source": name,
            "category": category,
            "title": getattr(entry, "title", "").strip(),
            "url": article_url,
            "url_hash": _hash(article_url or getattr(entry, "title", "")),
            "content": content[:2000],
            "published_at": _parse_date(entry),
        })
    return articles
