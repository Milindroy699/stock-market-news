"""Scraper for Zerodha Varsity — latest modules/chapters."""
import hashlib
from datetime import datetime
import httpx
from bs4 import BeautifulSoup


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


BASE = "https://zerodha.com/varsity"


async def fetch(max_items: int = 3) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(BASE, headers={"User-Agent": "StockMarketNewsBot/1.0"})
            resp.raise_for_status()
    except Exception as e:
        print(f"[Varsity] fetch failed — {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    for item in soup.select(".module-card, .chapter-card, article")[:max_items]:
        title_el = item.select_one("h2 a, h3 a, a")
        desc_el = item.select_one("p, .description")

        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        link = title_el.get("href", "")
        if link and not link.startswith("http"):
            link = "https://zerodha.com" + link
        content = desc_el.get_text(strip=True) if desc_el else ""

        articles.append({
            "source": "Varsity by Zerodha",
            "category": "education",
            "title": title,
            "url": link,
            "url_hash": _hash(link or title),
            "content": content[:2000],
            "published_at": datetime.utcnow(),
        })

    return articles
