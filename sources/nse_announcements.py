"""Scraper for NSE corporate announcements via NSE's public JSON API."""
import hashlib
from datetime import datetime
import httpx


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


NSE_API = "https://www.nseindia.com/api/corporate-announcements?index=equities"
NSE_BASE = "https://www.nseindia.com"


async def fetch(max_items: int = 10) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
    }
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # NSE requires a session cookie first
            await client.get(NSE_BASE, headers=headers)
            resp = await client.get(NSE_API, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"[NSEAnnouncements] fetch failed — {e}")
        return []

    articles = []
    announcements = data if isinstance(data, list) else data.get("data", [])
    for item in announcements[:max_items]:
        symbol = item.get("symbol", "")
        subject = item.get("subject", item.get("desc", ""))
        an_date = item.get("an_dt", item.get("date", ""))
        attachment = item.get("attchmntFile", "")
        link = f"https://www.nseindia.com/api/corporate-announcements?index=equities" if not attachment else f"https://archives.nseindia.com/corporate/{attachment}"

        title = f"[{symbol}] {subject}" if symbol else subject
        try:
            pub_date = datetime.strptime(an_date[:10], "%d-%b-%Y") if an_date else datetime.utcnow()
        except Exception:
            pub_date = datetime.utcnow()

        if title:
            articles.append({
                "source": "NSE Announcements",
                "category": "exchange",
                "title": title,
                "url": link,
                "url_hash": _hash(title + an_date),
                "content": subject,
                "published_at": pub_date,
            })

    return articles
