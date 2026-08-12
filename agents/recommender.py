"""
Generates swing + long-term stock recommendations.
If ANTHROPIC_API_KEY is set: uses Claude for rich thesis + targets.
Otherwise: rule-based signals from RSI, MACD, EMA, volume.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
from datetime import date
import config
from storage.db import get_session, Article, StockData, Recommendation, init_db


def _extract_json(text: str) -> str:
    """Strip markdown code fences if Claude wraps the JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.rstrip())
    return text.strip()

DISCLAIMER = (
    "AI/rule-generated recommendations are for educational and research purposes only. "
    "Not financial advice. Always do your own research before investing."
)

DISPLAY_NAMES = {
    "RELIANCE.NS": "Reliance Industries",
    "INFY.NS": "Infosys",
    "HDFCBANK.NS": "HDFC Bank",
    "TCS.NS": "TCS",
    "MARUTI.NS": "Maruti Suzuki",
    "ICICIBANK.NS": "ICICI Bank",
    "WIPRO.NS": "Wipro",
    "AXISBANK.NS": "Axis Bank",
    "SBIN.NS": "State Bank of India",
    "BAJFINANCE.NS": "Bajaj Finance",
}


# ── Rule-based engine ─────────────────────────────────────────────────────────

def _pct(value: float, pct: float) -> str:
    return f"{value * (1 + pct / 100):.0f}"


def _rule_swing_pick(ticker: str, row: StockData) -> dict | None:
    if not row or not row.close:
        return None
    sig = row.signals or {}
    rsi = row.rsi_14
    macd = sig.get("macd")
    trend = sig.get("trend")
    vol_spike = sig.get("volume_spike", False)
    close = row.close
    support = sig.get("support", close * 0.96)
    resistance = sig.get("resistance", close * 1.04)

    # BUY setup: oversold/neutral RSI + bullish MACD cross (allow downtrend when RSI is low)
    if rsi and rsi < 58 and macd == "bullish_cross":
        direction = "BUY"
        entry = f"{close * 0.99:.0f}–{close * 1.005:.0f}"
        t1 = _pct(close, 4)
        t2 = _pct(close, 8)
        sl = f"{support:.0f}" if support < close * 0.99 else _pct(close, -3)
        thesis = (
            f"Bullish MACD crossover with RSI at {rsi:.0f} — momentum turning up. "
            f"{'Volume spike confirms move. ' if vol_spike else ''}"
            f"Entry near support at {support:.0f}."
        )
        confidence = "High" if (rsi < 40 and vol_spike) else "Medium"

    # SELL setup: overbought RSI + bearish MACD
    elif rsi and rsi > 68 and macd == "bearish_cross":
        direction = "SELL SHORT"
        entry = f"{close * 1.005:.0f}–{close * 1.01:.0f}"
        t1 = _pct(close, -4)
        t2 = _pct(close, -7)
        sl = f"{resistance:.0f}" if resistance > close * 1.01 else _pct(close, 3)
        thesis = (
            f"Bearish MACD cross with RSI overbought at {rsi:.0f}. "
            f"Resistance at {resistance:.0f} likely to cap upside."
        )
        confidence = "Medium"

    else:
        return None

    return {
        "ticker": ticker,
        "display_name": DISPLAY_NAMES.get(ticker, ticker),
        "direction": direction,
        "entry_range": entry,
        "target_1": t1,
        "target_2": t2,
        "stop_loss": sl,
        "timeframe": "5–12 days",
        "thesis": thesis,
        "confidence": confidence,
    }


def _rule_longterm_pick(ticker: str, row: StockData) -> dict | None:
    if not row or not row.close:
        return None
    sig = row.signals or {}
    rsi = row.rsi_14
    trend = sig.get("trend")
    vs_200 = sig.get("vs_ema200")
    close = row.close

    # ACCUMULATE: price below EMA200 (value zone) with RSI not extremely oversold (not a falling knife)
    if vs_200 == "below" and rsi and 25 < rsi < 50:
        direction = "ACCUMULATE"
        entry_zone = f"{_pct(close, -3)}–{close:.0f}"
        target = _pct(close, 20)
        thesis = (
            f"Trading below 200-day EMA — historically a value accumulation zone for quality large-caps. "
            f"RSI at {rsi:.0f} suggests selling pressure is easing."
        )
        confidence = "Medium"

    # HOLD — healthy uptrend, no extreme valuation signals
    elif trend == "uptrend" and rsi and 40 < rsi < 65:
        direction = "HOLD"
        entry_zone = f"{close:.0f} (hold existing)"
        target = _pct(close, 15)
        thesis = (
            f"In a confirmed uptrend above EMA50 and EMA200. RSI at {rsi:.0f} — "
            f"momentum healthy without being overextended."
        )
        confidence = "Medium"

    else:
        return None

    return {
        "ticker": ticker,
        "display_name": DISPLAY_NAMES.get(ticker, ticker),
        "direction": direction,
        "entry_zone": entry_zone,
        "target_12m": target,
        "thesis": thesis,
        "confidence": confidence,
    }


def _rule_based_recommendations(stock_rows: dict) -> dict:
    swing_picks, longterm_radar = [], []

    for ticker, row in stock_rows.items():
        if not row:
            continue
        if len(swing_picks) < 5:
            pick = _rule_swing_pick(ticker, row)
            if pick:
                swing_picks.append(pick)
        if len(longterm_radar) < 5:
            lt = _rule_longterm_pick(ticker, row)
            if lt:
                longterm_radar.append(lt)

    return {"swing_picks": swing_picks, "longterm_radar": longterm_radar, "disclaimer": DISCLAIMER}


# ── Claude-powered engine ─────────────────────────────────────────────────────

def _build_stock_context(ticker: str, row: StockData | None) -> str:
    if not row:
        return f"{ticker}: No data"
    sig = row.signals or {}
    return (
        f"{ticker}: close={row.close:.0f} | RSI={row.rsi_14} | "
        f"trend={sig.get('trend','?')} | MACD={sig.get('macd','?')} | "
        f"vs_EMA20={sig.get('vs_ema20','?')} | vs_EMA50={sig.get('vs_ema50','?')} | "
        f"vs_EMA200={sig.get('vs_ema200','?')} | vol_spike={sig.get('volume_spike','?')} | "
        f"support={sig.get('support','?')} | resistance={sig.get('resistance','?')}"
    )


def _ai_recommendations(articles: list, stock_rows: dict, client) -> dict:
    SYSTEM_PROMPT = (
        "You are a senior equity research analyst for NSE/BSE Indian markets. "
        "Always respond with valid JSON only."
    )
    stock_ctx = "\n".join(_build_stock_context(t, stock_rows.get(t)) for t in config.WATCHLIST)
    news_ctx = "\n".join(
        f"[{a.source}] {a.title}: {(a.content or '')[:200]}"
        for a in articles[:15]
    )

    prompt = f"""Today: {date.today()}

=== TECHNICAL SIGNALS ===
{stock_ctx}

=== NEWS SENTIMENT ===
{news_ctx}

Generate trade ideas for Indian retail investors. Only use stocks from the watchlist.

Respond with JSON:
{{
  "swing_picks": [
    {{
      "ticker": "RELIANCE.NS",
      "display_name": "Reliance Industries",
      "direction": "BUY",
      "entry_range": "2980-3010",
      "target_1": "3080",
      "target_2": "3150",
      "stop_loss": "2940",
      "timeframe": "5-10 days",
      "thesis": "reason in 2 sentences",
      "confidence": "High|Medium|Low"
    }}
  ],
  "longterm_radar": [
    {{
      "ticker": "INFY.NS",
      "display_name": "Infosys",
      "direction": "ACCUMULATE",
      "entry_zone": "1420-1460",
      "target_12m": "1750",
      "thesis": "reason in 2 sentences",
      "confidence": "High|Medium|Low"
    }}
  ]
}}

Rules: 3-5 swing picks with stop_loss; 3-5 longterm ideas."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        result = json.loads(_extract_json(resp.content[0].text))
        result["disclaimer"] = DISCLAIMER
        return result
    except json.JSONDecodeError:
        print("[Recommender] JSON parse error — falling back to rule-based")
        return _rule_based_recommendations(stock_rows)


# ── Persist to DB ─────────────────────────────────────────────────────────────

def _save(recs: dict):
    today = date.today()
    with get_session() as session:
        for pick in recs.get("swing_picks", []):
            if not session.query(Recommendation).filter_by(
                ticker=pick["ticker"], rec_date=today, rec_type="swing"
            ).first():
                session.add(Recommendation(
                    rec_date=today, rec_type="swing",
                    ticker=pick["ticker"],
                    display_name=pick.get("display_name"),
                    direction=pick.get("direction"),
                    entry_range=pick.get("entry_range"),
                    target_1=pick.get("target_1"),
                    target_2=pick.get("target_2"),
                    stop_loss=pick.get("stop_loss"),
                    timeframe=pick.get("timeframe"),
                    thesis=pick.get("thesis"),
                    confidence=pick.get("confidence"),
                ))
        for pick in recs.get("longterm_radar", []):
            if not session.query(Recommendation).filter_by(
                ticker=pick["ticker"], rec_date=today, rec_type="longterm"
            ).first():
                session.add(Recommendation(
                    rec_date=today, rec_type="longterm",
                    ticker=pick["ticker"],
                    display_name=pick.get("display_name"),
                    direction=pick.get("direction"),
                    entry_range=pick.get("entry_zone", pick.get("entry_range")),
                    target_1=pick.get("target_12m", pick.get("target_1")),
                    thesis=pick.get("thesis"),
                    confidence=pick.get("confidence"),
                ))
        session.commit()


# ── Public entry point ────────────────────────────────────────────────────────

def run() -> dict:
    init_db()
    today = date.today()

    with get_session() as session:
        articles = session.query(Article).filter(Article.fetch_date == today).all()
        stock_rows = {
            t: session.query(StockData).filter_by(ticker=t, data_date=today).first()
            for t in config.WATCHLIST
        }

    if config.ANTHROPIC_API_KEY:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        recs = _ai_recommendations(articles, stock_rows, client)
        print("[Recommender] Used Claude AI")
    else:
        print("[Recommender] No API key — using rule-based signals")
        recs = _rule_based_recommendations(stock_rows)

    _save(recs)
    print(f"[Recommender] {len(recs.get('swing_picks',[]))} swing, {len(recs.get('longterm_radar',[]))} longterm saved")
    return recs


if __name__ == "__main__":
    result = run()
    for p in result.get("swing_picks", []):
        print(f"  {p['direction']} {p['display_name']} | Entry: {p['entry_range']} | T1: {p['target_1']} | SL: {p['stop_loss']}")
