"""
Summarises news articles into a daily digest.
If ANTHROPIC_API_KEY is set: uses Claude for full AI summaries.
Otherwise: falls back to rule-based extraction (top headlines + keyword sector detection).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
from datetime import date
import config
from storage.db import get_session, Article, DailyDigest, Transcript, init_db

# ── Sector keyword map for rule-based detection ───────────────────────────────
SECTOR_KEYWORDS = {
    "IT":      ["infosys", "tcs", "wipro", "hcl", "tech mahindra", "it sector", "software", "ai", "saas", "cloud"],
    "Banking": ["hdfc bank", "icici", "axis bank", "sbi", "kotak", "rbi", "npa", "credit", "loan", "deposit", "nbfc"],
    "Auto":    ["maruti", "tata motors", "bajaj auto", "hero moto", "m&m", "auto", "ev", "electric vehicle"],
    "FMCG":    ["hindustan unilever", "itc", "nestle", "dabur", "marico", "fmcg", "consumer"],
    "Pharma":  ["sun pharma", "dr reddy", "cipla", "divi", "pharma", "drug", "healthcare", "biocon"],
    "Energy":  ["reliance", "ongc", "ntpc", "oil", "gas", "power", "coal", "renewable", "solar"],
    "Metals":  ["tata steel", "jsw", "hindalco", "vedanta", "steel", "aluminum", "copper", "metal"],
    "Realty":  ["dlf", "godrej properties", "real estate", "realty", "housing", "property"],
}


def _rule_based_sector_pulse(articles: list) -> dict:
    """Count keyword hits per sector across all articles to determine sentiment."""
    combined = " ".join(
        (a.title + " " + (a.content or "")).lower()
        for a in articles
    )
    pulse = {}
    for sector, keywords in SECTOR_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in combined)
        if hits >= 3:
            pulse[sector] = "bullish"
        elif hits >= 1:
            pulse[sector] = "neutral"
        else:
            pulse[sector] = "neutral"
    return pulse


def _rule_based_digest(articles: list) -> dict:
    """Build a digest purely from article titles + excerpts, no AI."""
    # Prioritise premium sources, then news, then community
    priority = {"premium": 0, "analysis": 1, "news": 2, "broker": 3,
                "explainer": 4, "exchange": 5, "community": 6, "global": 7}
    sorted_articles = sorted(
        articles,
        key=lambda a: priority.get(a.category or "news", 9)
    )

    top_stories = []
    for a in sorted_articles[:10]:
        title = a.title.strip()
        # Use content excerpt as summary if available, else repeat the headline
        content = (a.content or "").strip()
        # Strip HTML tags
        content = re.sub(r"<[^>]+>", " ", content).strip()
        summary = content[:200] if content else title
        if not summary.endswith("."):
            summary = summary.rstrip(",;:") + "."
        top_stories.append({
            "headline": title,
            "summary": summary,
            "source": a.source,
        })

    sector_pulse = _rule_based_sector_pulse(articles)

    # Pick a macro theme from the top article
    macro = "Markets in focus — check the top stories for today's key themes."
    if top_stories:
        macro = f"Leading story: {top_stories[0]['headline']}"

    return {
        "top_stories": top_stories,
        "sector_pulse": sector_pulse,
        "macro_theme": macro,
    }


def _rule_based_transcript_brief(transcript) -> dict:
    """Extract a basic brief from a transcript without AI."""
    text = (transcript.transcript or "")
    sentences = [s.strip() for s in re.split(r"[.!?]", text) if len(s.strip()) > 40]
    insights = sentences[:5] if sentences else ["No transcript content available."]
    return {
        "source": transcript.source,
        "title": transcript.title or "",
        "main_topic": f"Video/podcast from {transcript.source}",
        "insights": insights,
        "stocks_mentioned": [],
    }


# ── Claude-powered functions (used when API key is available) ─────────────────

def _extract_json(text: str) -> str:
    """Strip markdown code fences if Claude wraps the JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.rstrip())
    return text.strip()


def _ai_summarise_news(articles: list, client) -> dict:
    SYSTEM_PROMPT = (
        "You are a concise financial news analyst specialising in Indian and global markets. "
        "Your audience is an Indian retail investor. "
        "Always respond with valid JSON only. No markdown, no preamble."
    )
    lines = []
    for i, a in enumerate(articles[:config.MAX_ARTICLES_FOR_DIGEST], 1):
        lines.append(f"{i}. [{a.source}] {a.title}\n   {(a.content or '')[:400]}")
    article_text = "\n\n".join(lines)

    prompt = f"""Here are today's financial news articles:

{article_text}

Respond with JSON in exactly this structure:
{{
  "top_stories": [
    {{"headline": "short headline", "summary": "2-sentence summary", "source": "source name"}}
  ],
  "sector_pulse": {{
    "IT": "bullish|bearish|neutral",
    "Banking": "bullish|bearish|neutral",
    "Auto": "bullish|bearish|neutral",
    "FMCG": "bullish|bearish|neutral",
    "Pharma": "bullish|bearish|neutral",
    "Energy": "bullish|bearish|neutral",
    "Metals": "bullish|bearish|neutral",
    "Realty": "bullish|bearish|neutral"
  }},
  "macro_theme": "One sentence: the dominant macro theme to watch this week"
}}

Include exactly 5 top stories. Pick the most market-moving news."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return json.loads(_extract_json(resp.content[0].text))
    except json.JSONDecodeError as e:
        print(f"[Summarizer] JSON parse error: {e}")
        return _rule_based_digest(articles)


def _ai_summarise_transcript(transcript, client) -> dict | None:
    SYSTEM_PROMPT = (
        "You are a concise financial news analyst. "
        "Always respond with valid JSON only."
    )
    prompt = f"""Summarise this podcast/video transcript for an Indian stock market investor.

Source: {transcript.source}
Title: {transcript.title}

Transcript:
{(transcript.transcript or '')[:4000]}

Respond with JSON only:
{{
  "source": "{transcript.source}",
  "title": "{transcript.title}",
  "main_topic": "one-line description",
  "insights": ["insight 1", "insight 2", "insight 3", "insight 4", "insight 5"],
  "stocks_mentioned": ["RELIANCE", "INFY"]
}}"""
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(_extract_json(resp.content[0].text))
    except Exception as e:
        print(f"[Summarizer] transcript AI failed for {transcript.title}: {e}")
        return _rule_based_transcript_brief(transcript)


# ── Public entry point ────────────────────────────────────────────────────────

def run() -> dict:
    init_db()
    today = date.today()

    with get_session() as session:
        articles = session.query(Article).filter(Article.fetch_date == today).all()
        transcripts = session.query(Transcript).filter(Transcript.fetch_date == today).all()

    ai_available = bool(config.ANTHROPIC_API_KEY)

    if ai_available:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        digest_data = _ai_summarise_news(articles, client)
        podcast_briefs = [b for t in transcripts if (b := _ai_summarise_transcript(t, client))]
        print("[Summarizer] Used Claude AI")
    else:
        print("[Summarizer] No API key — using rule-based fallback")
        digest_data = _rule_based_digest(articles)
        podcast_briefs = [_rule_based_transcript_brief(t) for t in transcripts]

    digest_data["podcast_briefs"] = podcast_briefs

    with get_session() as session:
        existing = session.query(DailyDigest).filter_by(digest_date=today).first()
        if existing:
            existing.top_stories = digest_data["top_stories"]
            existing.sector_pulse = digest_data["sector_pulse"]
            existing.macro_theme = digest_data["macro_theme"]
            existing.podcast_briefs = podcast_briefs
        else:
            session.add(DailyDigest(
                digest_date=today,
                top_stories=digest_data["top_stories"],
                sector_pulse=digest_data["sector_pulse"],
                macro_theme=digest_data.get("macro_theme", ""),
                podcast_briefs=podcast_briefs,
            ))
        session.commit()

    print(f"[Summarizer] Digest saved: {len(digest_data['top_stories'])} stories, {len(podcast_briefs)} podcast briefs")
    return digest_data


if __name__ == "__main__":
    result = run()
    for s in result.get("top_stories", []):
        print(f"  - {s['headline']}")
