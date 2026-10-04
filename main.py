"""Finance News RSS MCP Server

This MCP server provides tools to fetch and search finance news from major RSS feeds.
"""

from datetime import datetime
from typing import Any

import feedparser
import httpx
from fastmcp import FastMCP

from seekingalpha import build_thesis_inputs

# Initialize MCP server
mcp = FastMCP("Finance News RSS Server")

# Major finance news RSS feeds
RSS_FEEDS = {
    # Bloomberg - Markets/News feed
    "bloomberg": "https://feeds.bloomberg.com/markets/news.rss",

    # WSJ - Wall Street Journal Markets feed
    "wsj": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",

    # CNBC - Alternative feed URL
    "cnbc": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147",

    # Seeking Alpha - Financial news and analysis
    "seekingalpha": "https://seekingalpha.com/market_currents.xml",

    # MarketWatch - Top stories
    "marketwatch": "https://www.marketwatch.com/rss/topstories",

    # Financial Times - Home feed
    "ft": "https://www.ft.com/rss/home",
}


def fetch_feed(url: str, source_name: str) -> list[dict[str, Any]]:
    """Fetch and parse an RSS feed.

    Args:
        url: RSS feed URL
        source_name: Name of the news source

    Returns:
        List of article dictionaries
    """
    try:
        # Add user-agent header to avoid blocking
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = httpx.get(url, timeout=10.0, follow_redirects=True, headers=headers)
        response.raise_for_status()
        feed = feedparser.parse(response.text)

        articles = []
        for entry in feed.entries:
            # Extract published date
            published = "Unknown"
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6])
                    published = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (TypeError, ValueError):
                    published = getattr(entry, "published", "Unknown")
            elif hasattr(entry, "published"):
                published = entry.published

            # Extract description/summary
            description = ""
            if hasattr(entry, "summary"):
                description = entry.summary
            elif hasattr(entry, "description"):
                description = entry.description

            articles.append({
                "title": entry.get("title", "No title"),
                "link": entry.get("link", ""),
                "published_date": published,
                "description": description,
                "source_name": source_name,
            })

        return articles

    except Exception as e:
        # Log error but don't crash - just return empty list
        print(f"Error fetching {source_name}: {e}")
        return []


@mcp.tool()
def get_latest_finance_news(limit: int = 10, source: str = "all") -> list[dict[str, Any]]:
    """Get the latest finance news from RSS feeds.

    Args:
        limit: Maximum number of articles to return (default: 10)
        source: News source to fetch from. Options: "all", "bloomberg", "wsj",
                "cnbc", "seekingalpha", "marketwatch", "ft" (default: "all")

    Returns:
        List of articles with title, link, published_date, description, and source_name
    """
    all_articles = []

    # Determine which feeds to fetch
    if source == "all":
        feeds_to_fetch = RSS_FEEDS.items()
    elif source in RSS_FEEDS:
        feeds_to_fetch = [(source, RSS_FEEDS[source])]
    else:
        return [{"error": f"Unknown source: {source}. Available: {', '.join(RSS_FEEDS.keys())}"}]

    # Fetch from selected feeds
    for source_name, url in feeds_to_fetch:
        articles = fetch_feed(url, source_name)
        all_articles.extend(articles)

    # Sort by source name and return limited results
    all_articles.sort(key=lambda x: x["source_name"])

    return all_articles[:limit]


@mcp.tool()
def search_finance_news(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search finance news across all RSS feeds by keyword.

    Args:
        query: Search keyword to find in article titles or descriptions
        limit: Maximum number of matching articles to return (default: 10)

    Returns:
        List of matching articles with title, link, published_date, description, and source_name
    """
    if not query:
        return [{"error": "Query parameter is required"}]

    query_lower = query.lower()
    all_articles = []

    # Fetch from all feeds
    for source_name, url in RSS_FEEDS.items():
        articles = fetch_feed(url, source_name)
        all_articles.extend(articles)

    # Filter articles by query
    matching_articles = []
    for article in all_articles:
        title = article.get("title", "").lower()
        description = article.get("description", "").lower()

        if query_lower in title or query_lower in description:
            matching_articles.append(article)

    return matching_articles[:limit]


@mcp.tool()
def get_seekingalpha_ticker_thesis(ticker: str, limit: int = 10) -> dict[str, Any]:
    """Gather a ticker's latest Seeking Alpha analysis articles to build a Buy/Hold/Sell view.

    Returns the articles (title, author, date, url, summary, keyword-based rating cue), a
    bullish/neutral/bearish tally, and instructions for writing the thesis. Set
    SA_RAPIDAPI_KEY for article summaries; without it only titles are available.

    Args:
        ticker: Stock symbol, e.g. "AAPL" (see https://seekingalpha.com/symbol/<ticker>)
        limit: Number of articles to use, 1-10 (default: 10)

    Returns:
        Dict with ticker, provider, stance_tally, articles, warnings and instructions
    """
    return build_thesis_inputs(ticker, limit)


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
