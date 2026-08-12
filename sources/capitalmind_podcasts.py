"""Scraper for Capitalmind Podcast listing page."""
import hashlib
from datetime import datetime
import httpx
from bs4 import BeautifulSoup


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


BASE_URL = "https://www.capitalmind.in"
PODCAST_PAGE = f"{BASE_URL}/podcasts/page/1"


async def fetch(max_items: int = 3) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(PODCAST_PAGE, headers={"User-Agent": "StockMarketNewsBot/1.0"})
            resp.raise_for_status()
    except Exception as e:
        print(f"[CapitalmindPodcasts] fetch failed — {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    for card in soup.select("article, .post, .entry")[:max_items]:
        title_el = card.select_one("h2 a, h3 a, .entry-title a")
        excerpt_el = card.select_one(".entry-content p, .entry-excerpt, p")

        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        link = title_el.get("href", "")
        if link and not link.startswith("http"):
            link = BASE_URL + link
        content = excerpt_el.get_text(strip=True) if excerpt_el else ""

        articles.append({
            "source": "Capitalmind Podcasts",
            "category": "podcast",
            "title": title,
            "url": link,
            "url_hash": _hash(link or title),
            "content": content[:2000],
            "published_at": datetime.utcnow(),
            "is_podcast": True,
        })

    return articles
