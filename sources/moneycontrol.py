"""Scraper for Moneycontrol markets page (RSS is blocked, direct page is accessible)."""
import hashlib
import re
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
MC_URL = "https://www.moneycontrol.com/news/business/markets/"


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


async def fetch(max_items: int = 5) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(MC_URL, headers={"User-Agent": BROWSER_UA})
            resp.raise_for_status()
    except Exception as e:
        print(f"[Moneycontrol] fetch failed — {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    # Moneycontrol news list items
    for item in soup.select("li.clearfix, .news_main_box, article.article_box")[:max_items]:
        title_el = item.select_one("h2 a, h3 a, .article_title a, a[href*='/news/']")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        link = title_el.get("href", "")
        if link and not link.startswith("http"):
            link = "https://www.moneycontrol.com" + link

        desc_el = item.select_one("p, .article_desc")
        content = desc_el.get_text(strip=True) if desc_el else ""

        if title and "/news/" in link:
            articles.append({
                "source": "Moneycontrol",
                "category": "news",
                "title": title,
                "url": link,
                "url_hash": _hash(link),
                "content": content[:2000],
                "published_at": datetime.utcnow(),
            })

    return articles
