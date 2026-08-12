"""
Fetches The Ken stories using curl_cffi to bypass Cloudflare TLS fingerprinting.
Requires THE_KEN_COOKIE_STRING set in .env (full Cookie: header value from DevTools).
"""
import hashlib
import re
from datetime import datetime
from bs4 import BeautifulSoup
import config


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _parse_ken_cookies() -> dict:
    cookies = {}
    for part in config.THE_KEN_COOKIE_STRING.split(";"):
        if "=" in part:
            k, _, v = part.strip().partition("=")
            cookies[k.strip()] = v.strip()
    return cookies


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


async def fetch(max_items: int = 5) -> list[dict]:
    if not config.THE_KEN_COOKIE_STRING:
        print("[TheKen] No cookie configured — skipping. Set THE_KEN_COOKIE_STRING in .env")
        return []

    try:
        from curl_cffi.requests import AsyncSession
    except ImportError:
        print("[TheKen] curl_cffi not installed — run: pip install curl_cffi")
        return []

    cookies = _parse_ken_cookies()
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://the-ken.com/",
    }

    urls_to_try = [
        "https://the-ken.com/stories/",
        "https://the-ken.com/",
        "https://the-ken.com/the-daily-brief/",
    ]

    html = None
    fetched_url = None
    async with AsyncSession(impersonate="chrome124") as session:
        for url in urls_to_try:
            try:
                resp = await session.get(url, headers=headers, cookies=cookies, timeout=20)
                if resp.status_code == 200:
                    html = resp.text
                    fetched_url = url
                    break
                else:
                    print(f"[TheKen] {url}: {resp.status_code}")
            except Exception as e:
                print(f"[TheKen] {url}: {e}")

    if not html:
        print("[TheKen] All URLs failed — cookies may have expired, please refresh them in .env")
        return []

    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen = set()

    # The Ken article slugs live under specific newsletter section prefixes
    ARTICLE_PREFIXES = (
        "/kaching/", "/long-and-short/", "/trade-tricks/",
        "/story/", "/ka-ching/", "/intermission/",
    )

    all_links = soup.find_all("a", href=True)
    for a in all_links:
        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://the-ken.com" + href

        # Strip query strings and URL fragments for deduplication
        canonical = href.split("?")[0].split("#")[0].rstrip("/")

        if "the-ken.com" not in canonical:
            continue
        path = canonical.replace("https://the-ken.com", "")

        # Must match one of the known article path prefixes
        if not any(path.startswith(pfx) for pfx in ARTICLE_PREFIXES):
            continue
        # Must have a real article slug — exclude section index pages like /stories or /all
        slug_part = path.split("/")[-1]
        RESERVED_SLUGS = {"stories", "all", "all-stories", "archive", ""}
        if slug_part in RESERVED_SLUGS or len(slug_part) < 10:
            continue
        if canonical in seen:
            continue

        title = a.get_text(strip=True)
        # Walk up to find a better h2/h3 title
        parent = a.parent
        for _ in range(4):
            if parent is None:
                break
            h = parent.find(["h2", "h3"])
            if h:
                t = h.get_text(strip=True)
                if len(t) > 20:
                    title = t
                    break
            parent = parent.parent

        if not title or len(title) < 15:
            continue

        seen.add(canonical)
        articles.append({
            "source": "The Ken",
            "category": "premium",
            "title": title,
            "url": canonical,
            "url_hash": _hash(canonical),
            "content": "",
            "published_at": datetime.utcnow(),
        })

        if len(articles) >= max_items:
            break

    print(f"[TheKen] Fetched {len(articles)} articles from {fetched_url}")
    return articles
