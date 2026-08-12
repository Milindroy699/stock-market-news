"""Scraper for Zerodha Daily Brief — https://thedailybrief.zerodha.com/"""
import hashlib
from datetime import datetime
import httpx
from bs4 import BeautifulSoup


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


async def fetch() -> list[dict]:
    url = "https://thedailybrief.zerodha.com/"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "StockMarketNewsBot/1.0"})
            resp.raise_for_status()
    except Exception as e:
        print(f"[ZerodhaDailyBrief] fetch failed — {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    # The Daily Brief lists recent posts — grab the first few article cards
    for post in soup.select("article, .post, .gh-card")[:5]:
        title_el = post.select_one("h2, h3, .gh-card-title")
        link_el = post.select_one("a[href]")
        excerpt_el = post.select_one("p, .gh-card-excerpt")

        title = title_el.get_text(strip=True) if title_el else ""
        link = link_el["href"] if link_el else url
        if link.startswith("/"):
            link = "https://thedailybrief.zerodha.com" + link
        content = excerpt_el.get_text(strip=True) if excerpt_el else ""

        if title:
            articles.append({
                "source": "Zerodha Daily Brief",
                "category": "broker",
                "title": title,
                "url": link,
                "url_hash": _hash(link),
                "content": content[:2000],
                "published_at": datetime.utcnow(),
            })

    return articles
