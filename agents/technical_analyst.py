"""Computes technical indicators for each stock using pure pandas (no pandas-ta)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
import pandas as pd
import config
from agents.market_data import fetch_ohlcv
from storage.db import get_session, StockData, init_db


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def _bbands(series: pd.Series, period: int = 20):
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    return mid + 2 * std, mid - 2 * std


def compute_indicators(df: pd.DataFrame) -> dict:
    """Return a dict of indicator values for the most recent row."""
    if df is None or len(df) < 20:
        return {}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    rsi = _rsi(close, 14)
    macd_line, signal_line, hist = _macd(close)
    bb_upper, bb_lower = _bbands(close, 20)
    ema20 = _ema(close, 20)
    ema50 = _ema(close, 50)
    ema200 = _ema(close, 200)

    def last_val(s):
        v = s.dropna()
        return round(float(v.iloc[-1]), 4) if not v.empty else None

    result = {
        "rsi_14":     last_val(rsi),
        "macd":       last_val(macd_line),
        "macd_signal": last_val(signal_line),
        "macd_hist":  last_val(hist),
        "bb_upper":   last_val(bb_upper),
        "bb_lower":   last_val(bb_lower),
        "ema_20":     last_val(ema20),
        "ema_50":     last_val(ema50),
        "ema_200":    last_val(ema200),
    }

    cur_close = float(close.iloc[-1])
    signals = {}

    if result["rsi_14"]:
        r = result["rsi_14"]
        signals["rsi"] = "oversold" if r < 30 else "overbought" if r > 70 else "neutral"

    if result["macd"] is not None and result["macd_signal"] is not None:
        signals["macd"] = "bullish_cross" if result["macd"] > result["macd_signal"] else "bearish_cross"

    if result["ema_20"]:
        signals["vs_ema20"] = "above" if cur_close > result["ema_20"] else "below"
    if result["ema_50"]:
        signals["vs_ema50"] = "above" if cur_close > result["ema_50"] else "below"
    if result["ema_200"]:
        signals["vs_ema200"] = "above" if cur_close > result["ema_200"] else "below"

    above_50 = signals.get("vs_ema50") == "above"
    above_200 = signals.get("vs_ema200") == "above"
    if above_50 and above_200:
        signals["trend"] = "uptrend"
    elif not above_50 and not above_200:
        signals["trend"] = "downtrend"
    else:
        signals["trend"] = "mixed"

    avg_vol = float(volume.iloc[-20:].mean())
    cur_vol = float(volume.iloc[-1])
    signals["volume_spike"] = cur_vol > avg_vol * 1.5

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


def run_for_all() -> dict:
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
