"""Fetches OHLCV data for watchlist + indices from Yahoo Finance (NSE/BSE)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
import yfinance as yf
import pandas as pd
import config
from storage.db import get_session, StockData, MarketSnapshot, init_db


def fetch_ohlcv(ticker: str, days: int = 60) -> pd.DataFrame | None:
    end = date.today()
    start = end - timedelta(days=days)
    try:
        df = yf.download(ticker, start=str(start), end=str(end), progress=False, auto_adjust=True)
        if df.empty:
            return None
        # yfinance 1.x returns MultiIndex columns like ('Close', 'TICKER') — flatten to lowercase field name
        if isinstance(df.columns[0], tuple):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        df = df.dropna(subset=["close"])
        return df if not df.empty else None
    except Exception as e:
        print(f"[MarketData] {ticker}: fetch failed — {e}")
        return None


def fetch_index_snapshot() -> dict:
    """Return a dict of {name: {price, change, change_pct}} for configured indices."""
    snapshot = {}
    for name, ticker in config.INDICES.items():
        try:
            info = yf.Ticker(ticker).fast_info
            price = round(info.last_price, 2)
            prev_close = round(info.previous_close, 2)
            change = round(price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
            snapshot[name] = {"price": price, "change": change, "change_pct": change_pct}
        except Exception as e:
            print(f"[MarketData] Index {name}: {e}")
            snapshot[name] = {"price": 0, "change": 0, "change_pct": 0}
    return snapshot


def save_index_snapshot(indices: dict):
    today = date.today()
    with get_session() as session:
        existing = session.query(MarketSnapshot).filter_by(snapshot_date=today).first()
        if existing:
            existing.indices = indices
        else:
            session.add(MarketSnapshot(snapshot_date=today, indices=indices))
        session.commit()


def save_stock_ohlcv(ticker: str, df: pd.DataFrame):
    """Persist latest row of OHLCV to DB (filled by technical_analyst later)."""
    if df is None or df.empty:
        return
    row_data = df.iloc[-1]
    today = date.today()
    with get_session() as session:
        existing = session.query(StockData).filter_by(ticker=ticker, data_date=today).first()
        if existing:
            return
        session.add(StockData(
            ticker=ticker,
            data_date=today,
            open=float(row_data.get("open", 0)),
            high=float(row_data.get("high", 0)),
            low=float(row_data.get("low", 0)),
            close=float(row_data.get("close", 0)),
            volume=float(row_data.get("volume", 0)),
        ))
        session.commit()


def run() -> dict:
    init_db()
    indices = fetch_index_snapshot()
    save_index_snapshot(indices)

    stock_dfs = {}
    for ticker in config.WATCHLIST:
        df = fetch_ohlcv(ticker, days=60)
        if df is not None:
            save_stock_ohlcv(ticker, df)
            stock_dfs[ticker] = df
            print(f"[MarketData] {ticker}: {len(df)} rows fetched")
        else:
            print(f"[MarketData] {ticker}: no data")

    return {"indices": indices, "stock_dfs": stock_dfs}


if __name__ == "__main__":
    result = run()
    for name, snap in result["indices"].items():
        print(f"  {name}: {snap['price']} ({snap['change_pct']:+.2f}%)")
