import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

WATCHLIST = [
    "RELIANCE.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "TCS.NS",
    "MARUTI.NS",
    "ICICIBANK.NS",
    "WIPRO.NS",
    "AXISBANK.NS",
    "SBIN.NS",
    "BAJFINANCE.NS",
]

INDICES = {
    "Nifty 50": "^NSEI",
    "Sensex": "^BSESN",
    "Bank Nifty": "^NSEBANK",
    "Nifty IT": "^CNXIT",
    "Nifty Pharma": "^CNXPHARMA",
}

YOUTUBE_CHANNELS = [
    "https://www.youtube.com/@marketsbyzerodha",
    "https://www.youtube.com/@soicfinance",
]

SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:00")
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "8000")))

THE_KEN_COOKIE_STRING = os.getenv("THE_KEN_COOKIE_STRING", "")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "StockMarketNewsBot/1.0")

RSS_SOURCES = [
    # The Ken is paywalled — only article titles/excerpts come through, still useful for topic awareness
    {"name": "The Ken", "url": "https://the-ken.com/feed/", "category": "premium"},
    {"name": "ET Markets", "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "category": "news"},
    {"name": "ET Prime Markets", "url": "https://economictimes.indiatimes.com/prime/rssfeeds/1177578094.cms", "category": "news"},
    # Capitalmind RSS redirects to premium; use capitalmind_podcasts scraper instead
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "category": "global"},
    {"name": "Zerodha Blog", "url": "https://zerodha.com/z-connect/feed", "category": "broker"},
    # Moneycontrol blocks all non-browser HTTP requests; removed from auto-fetch
    # {"name": "Moneycontrol", "url": "https://www.moneycontrol.com/rss/MCtopnews.xml", "category": "news"},
    {"name": "Mint Markets", "url": "https://www.livemint.com/rss/markets", "category": "news"},
    {"name": "CNBC TV18 Markets", "url": "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/market.xml", "category": "news"},
    {"name": "CNBC TV18 Economy", "url": "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/economy.xml", "category": "news"},
    {"name": "Finshots", "url": "https://finshots.in/feed/", "category": "explainer"},
    {"name": "ValuePickr", "url": "https://forum.valuepickr.com/latest.rss", "category": "community"},
]

SCRAPE_SOURCES = [
    {"name": "Zerodha Daily Brief", "url": "https://thedailybrief.zerodha.com/", "type": "daily_brief"},
    {"name": "NSE Announcements", "url": "https://www.nseindia.com/companies-listing/corporate-filings-announcements", "type": "nse"},
    {"name": "Capitalmind Podcasts", "url": "https://www.capitalmind.in/podcasts/page/1", "type": "podcast_page"},
    {"name": "Varsity by Zerodha", "url": "https://zerodha.com/varsity/", "type": "education"},
]

MAX_ARTICLES_PER_SOURCE = 5
MAX_ARTICLES_FOR_DIGEST = 20
AUDIO_DOWNLOAD_DIR = "audio_cache"
DB_PATH = "market_news.db"
