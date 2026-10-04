"""Seeking Alpha ticker research helpers.

Seeking Alpha blocks automated access to its ticker pages, article pages and JSON API
(PerimeterX captcha), so articles come from one of two providers:

- "rapidapi": a licensed Seeking Alpha API on RapidAPI (set SA_RAPIDAPI_KEY). Returns
  analysis articles with summaries.
- "rss": the public per-ticker feed. Needs no key, but returns titles, authors and dates
  only, and few of its items are analysis articles.
"""

import os
import re
from typing import Any

import feedparser
import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TICKER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]{0,9}$")
RSS_URL = "https://seekingalpha.com/api/sa/combined/{symbol}.xml"
RAPIDAPI_HOST = os.environ.get("SA_RAPIDAPI_HOST", "seeking-alpha.p.rapidapi.com")

# Ordered so that "strong buy" is matched before "buy", etc.
RATING_PATTERNS = [
    ("strong_buy", re.compile(r"\bstrong[\s-]+buy\b", re.I)),
    ("strong_sell", re.compile(r"\bstrong[\s-]+sell\b", re.I)),
    ("buy", re.compile(r"\bbuy\b|\bupgrade\b|\bbullish\b|\boutperform\b", re.I)),
    ("sell", re.compile(r"\bsell\b|\bdowngrade\b|\bbearish\b|\bunderperform\b|betting against", re.I)),
    ("hold", re.compile(r"\bhold\b|\bneutral\b|\bwait\b", re.I)),
]
STANCE = {
    "strong_buy": "bullish", "buy": "bullish",
    "hold": "neutral",
    "sell": "bearish", "strong_sell": "bearish",
}


def validate_ticker(ticker: str) -> str | None:
    """Return the normalized ticker, or None if it is not a plausible symbol."""
    ticker = (ticker or "").strip()
    return ticker.upper() if TICKER_RE.match(ticker) else None


def detect_rating(text: str) -> str | None:
    """Return the first rating cue found in text (e.g. 'strong_buy', 'sell'), if any."""
    for rating, pattern in RATING_PATTERNS:
        if pattern.search(text):
            return rating
    return None


def parse_rss(xml: str, symbol: str, limit: int) -> list[dict[str, Any]]:
    """Extract analysis articles (not market-current news items) from the ticker feed."""
    articles = []
    for entry in feedparser.parse(xml).entries:
        link = entry.get("link", "")
        if "/article/" not in link:
            continue
        title = entry.get("title", "")
        articles.append({
            "title": title,
            "author": entry.get("author", "") or entry.get("sa_author_name", ""),
            "published": entry.get("published", ""),
            "url": link.split("?")[0],
            "summary": "",
            "rating_cue": detect_rating(title),
        })
        if len(articles) >= limit:
            break
    return articles


def fetch_rss(symbol: str, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    warnings = [
        "RSS provider returns titles only (no article summaries) and few analysis "
        "articles per ticker. Set SA_RAPIDAPI_KEY for fuller coverage."
    ]
    response = httpx.get(
        RSS_URL.format(symbol=symbol), timeout=15.0, follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return parse_rss(response.text, symbol, limit), warnings


def parse_rapidapi_list(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    """Map the RapidAPI `analysis/v2/list` JSON:API payload to our article shape."""
    authors = {
        item.get("id"): item.get("attributes", {}).get("nick", "")
        for item in payload.get("included", []) if item.get("type") == "author"
    }
    articles = []
    for item in payload.get("data", [])[:limit]:
        attrs = item.get("attributes", {})
        author_id = item.get("relationships", {}).get("author", {}).get("data", {}).get("id")
        link = item.get("links", {}).get("self", f"/article/{item.get('id')}")
        title = attrs.get("title", "")
        articles.append({
            "id": item.get("id"),
            "title": title,
            "author": authors.get(author_id, ""),
            "published": attrs.get("publishOn", ""),
            "url": f"https://seekingalpha.com{link}",
            "summary": "",
            "rating_cue": detect_rating(title),
        })
    return articles


def parse_rapidapi_details(payload: dict[str, Any]) -> str:
    """Pull the author's bullet summary from `analysis/v2/get-details`, if present."""
    summary = payload.get("data", {}).get("attributes", {}).get("summary", [])
    if isinstance(summary, list):
        return " ".join(str(s).strip() for s in summary if s)
    return str(summary or "")


def fetch_rapidapi(symbol: str, limit: int, key: str) -> tuple[list[dict[str, Any]], list[str]]:
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": RAPIDAPI_HOST}
    base = f"https://{RAPIDAPI_HOST}"
    warnings: list[str] = []

    response = httpx.get(
        f"{base}/analysis/v2/list", timeout=20.0, headers=headers,
        params={"id": symbol.lower(), "size": limit, "number": 1},
    )
    response.raise_for_status()
    articles = parse_rapidapi_list(response.json(), limit)

    for article in articles:
        try:
            detail = httpx.get(
                f"{base}/analysis/v2/get-details", timeout=20.0, headers=headers,
                params={"id": article["id"]},
            )
            detail.raise_for_status()
            article["summary"] = parse_rapidapi_details(detail.json())
            article["rating_cue"] = detect_rating(f"{article['title']} {article['summary']}")
        except Exception as e:
            warnings.append(f"No summary for article {article['id']}: {e}")
    return articles, warnings


def tally_stances(articles: list[dict[str, Any]]) -> dict[str, int]:
    tally = {"bullish": 0, "neutral": 0, "bearish": 0, "unclassified": 0}
    for article in articles:
        tally[STANCE.get(article["rating_cue"], "unclassified")] += 1
    return tally


THESIS_INSTRUCTIONS = (
    "Using only the articles above, write for {symbol}: (1) the core elements of a "
    "Buy/Strong Buy thesis, (2) a Hold thesis, (3) a Sell/Strong Sell thesis, citing "
    "article titles/authors for each point, then (4) where the weight of opinion sits. "
    "rating_cue is a keyword heuristic, so verify it against each summary. If summaries "
    "are empty or few articles came back, say the view is thin. This is a summary of "
    "third-party opinion, not investment advice."
)


def build_thesis_inputs(ticker: str, limit: int = 10) -> dict[str, Any]:
    symbol = validate_ticker(ticker)
    if not symbol:
        return {"error": f"Invalid ticker: {ticker!r}. Use a symbol like AAPL or BRK.B."}
    limit = max(1, min(limit, 10))

    key = os.environ.get("SA_RAPIDAPI_KEY")
    provider = "rapidapi" if key else "rss"
    try:
        articles, warnings = fetch_rapidapi(symbol, limit, key) if key else fetch_rss(symbol, limit)
    except Exception as e:
        return {"error": f"Failed to fetch Seeking Alpha data for {symbol} via {provider}: {e}"}

    if not articles:
        warnings.append(f"No analysis articles found for {symbol}.")
    return {
        "ticker": symbol,
        "source_page": f"https://seekingalpha.com/symbol/{symbol}/analysis",
        "provider": provider,
        "article_count": len(articles),
        "stance_tally": tally_stances(articles),
        "articles": articles,
        "warnings": warnings,
        "instructions": THESIS_INSTRUCTIONS.format(symbol=symbol),
    }
