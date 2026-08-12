"""Computes technical indicators for each stock and updates DB + returns signals."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
import pandas as pd
import pandas_ta as ta
import config
from agents.market_data import fetch_ohlcv
from storage.db import get_session, StockData, init_db


def compute_indicators(df: pd.DataFrame) -> dict:
    """Return a dict of indicator values for the most recent row."""
    if df is None or len(df) < 20:
        return {}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    rsi = ta.rsi(close, length=14)
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    bb = ta.bbands(close, length=20)
    ema20 = ta.ema(close, length=20)
    ema50 = ta.ema(close, length=50)
    ema200 = ta.ema(close, length=200)

    last = -1
    result = {
        "rsi_14": round(float(rsi.iloc[last]), 2) if rsi is not None and not rsi.empty else None,
        "macd": None,
        "macd_signal": None,
        "macd_hist": None,
        "bb_upper": None,
        "bb_lower": None,
        "ema_20": round(float(ema20.iloc[last]), 2) if ema20 is not None else None,
        "ema_50": round(float(ema50.iloc[last]), 2) if ema50 is not None and len(ema50.dropna()) > 0 else None,
        "ema_200": round(float(ema200.iloc[last]), 2) if ema200 is not None and len(ema200.dropna()) > 0 else None,
    }

    if macd_df is not None and not macd_df.empty:
        cols = macd_df.columns.tolist()
        result["macd"] = round(float(macd_df[cols[0]].iloc[last]), 4)
        result["macd_signal"] = round(float(macd_df[cols[1]].iloc[last]), 4)
        result["macd_hist"] = round(float(macd_df[cols[2]].iloc[last]), 4)

    if bb is not None and not bb.empty:
        cols = bb.columns.tolist()
        result["bb_upper"] = round(float(bb[cols[0]].iloc[last]), 2)
        result["bb_lower"] = round(float(bb[cols[2]].iloc[last]), 2)

    # Derive readable signals
    cur_close = float(close.iloc[last])
    signals = {}

    if result["rsi_14"]:
        r = result["rsi_14"]
        if r < 30:
            signals["rsi"] = "oversold"
        elif r > 70:
            signals["rsi"] = "overbought"
        else:
            signals["rsi"] = "neutral"

    if result["macd"] and result["macd_signal"]:
        signals["macd"] = "bullish_cross" if result["macd"] > result["macd_signal"] else "bearish_cross"

    if result["ema_20"]:
        signals["vs_ema20"] = "above" if cur_close > result["ema_20"] else "below"
    if result["ema_50"]:
        signals["vs_ema50"] = "above" if cur_close > result["ema_50"] else "below"
    if result["ema_200"]:
        signals["vs_ema200"] = "above" if cur_close > result["ema_200"] else "below"

    # Trend: price above both EMA50 and EMA200 = uptrend
    above_50 = signals.get("vs_ema50") == "above"
    above_200 = signals.get("vs_ema200") == "above"
    if above_50 and above_200:
        signals["trend"] = "uptrend"
    elif not above_50 and not above_200:
        signals["trend"] = "downtrend"
    else:
        signals["trend"] = "mixed"

    # Volume spike: today's volume > 1.5x 20-day average
    avg_vol = float(volume.iloc[-20:].mean())
    cur_vol = float(volume.iloc[last])
    signals["volume_spike"] = cur_vol > avg_vol * 1.5

    # Simple support/resistance: recent 20-day low/high
    signals["support"] = round(float(low.iloc[-20:].min()), 2)
    signals["resistance"] = round(float(high.iloc[-20:].max()), 2)

    result["signals"] = signals
    return result


def update_stock_indicators(ticker: str, df: pd.DataFrame) -> dict:
    indicators = compute_indicators(df)
    if not indicators:
        return {}

    today = date.today()
    with get_session() as session:
        row = session.query(StockData).filter_by(ticker=ticker, data_date=today).first()
        if row:
            for k, v in indicators.items():
                if k != "signals" and hasattr(row, k):
                    setattr(row, k, v)
            row.signals = indicators.get("signals", {})
        session.commit()

    return indicators


def run_for_all() -> dict[str, dict]:
    init_db()
    results = {}
    for ticker in config.WATCHLIST:
        df = fetch_ohlcv(ticker, days=60)
        if df is not None:
            ind = update_stock_indicators(ticker, df)
            results[ticker] = ind
            sig = ind.get("signals", {})
            print(f"[TA] {ticker}: trend={sig.get('trend')} rsi={ind.get('rsi_14')} macd={sig.get('macd')}")
    return results


if __name__ == "__main__":
    run_for_all()
