import os
from datetime import date, datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float,
    Date, DateTime, Boolean, JSON, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, Session
import config

Base = declarative_base()
_engine = None


def _db_url() -> str:
    # Render (and other cloud providers) set DATABASE_URL with postgres://
    url = os.getenv("DATABASE_URL", "")
    if url.startswith("postgres://"):
        # SQLAlchemy 2.x requires postgresql://
        url = url.replace("postgres://", "postgresql://", 1)
    if url:
        return url
    return f"sqlite:///{config.DB_PATH}"


def get_engine():
    global _engine
    if _engine is None:
        url = _db_url()
        kwargs = {"echo": False}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
    return _engine


def init_db():
    Base.metadata.create_all(get_engine())


def get_session() -> Session:
    return Session(get_engine())


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("url_hash", name="uq_article_url"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False)
    category = Column(String(50))
    title = Column(Text, nullable=False)
    url = Column(Text)
    url_hash = Column(String(64), nullable=False)
    content = Column(Text)
    published_at = Column(DateTime)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    fetch_date = Column(Date, default=date.today)


class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (UniqueConstraint("video_id", name="uq_transcript_video"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100))
    video_id = Column(String(100), nullable=False)
    title = Column(Text)
    url = Column(Text)
    transcript = Column(Text)
    duration_seconds = Column(Integer)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    fetch_date = Column(Date, default=date.today)


class DailyDigest(Base):
    __tablename__ = "daily_digests"
    __table_args__ = (UniqueConstraint("digest_date", name="uq_digest_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_date = Column(Date, nullable=False)
    top_stories = Column(JSON)        # list of {headline, summary, source}
    sector_pulse = Column(JSON)       # {sector: "bullish"|"bearish"|"neutral"}
    macro_theme = Column(Text)
    podcast_briefs = Column(JSON)     # list of {source, title, insights}
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_date", name="uq_snapshot_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False)
    indices = Column(JSON)            # {"Nifty 50": {"price": 24821, "change": 108, "change_pct": 0.44}}
    fii_net = Column(Float)           # FII net buying in crores
    dii_net = Column(Float)           # DII net buying in crores
    created_at = Column(DateTime, default=datetime.utcnow)


class StockData(Base):
    __tablename__ = "stock_data"
    __table_args__ = (UniqueConstraint("ticker", "data_date", name="uq_stock_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(30), nullable=False)
    data_date = Column(Date, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    rsi_14 = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)
    bb_upper = Column(Float)
    bb_lower = Column(Float)
    ema_20 = Column(Float)
    ema_50 = Column(Float)
    ema_200 = Column(Float)
    signals = Column(JSON)            # {trend, momentum, volume_spike, support, resistance}


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("ticker", "rec_date", "rec_type", name="uq_rec"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    rec_date = Column(Date, nullable=False)
    rec_type = Column(String(20), nullable=False)   # "swing" | "longterm"
    ticker = Column(String(30), nullable=False)
    display_name = Column(String(100))
    direction = Column(String(20))                  # BUY | SELL | ACCUMULATE | AVOID
    entry_range = Column(String(50))
    target_1 = Column(String(30))
    target_2 = Column(String(30))
    stop_loss = Column(String(30))
    timeframe = Column(String(50))
    thesis = Column(Text)
    confidence = Column(String(20))                 # High | Medium | Low
    created_at = Column(DateTime, default=datetime.utcnow)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(Date, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    success = Column(Boolean, default=False)
    error_message = Column(Text)
    articles_fetched = Column(Integer, default=0)
    transcripts_fetched = Column(Integer, default=0)
