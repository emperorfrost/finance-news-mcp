# Finance News RSS MCP Server

A Model Context Protocol (MCP) server that provides real-time finance news from major RSS feeds. Built with [FastMCP](https://github.com/jlowin/fastmcp) to demonstrate MCP basics.

## What This MCP Does

This MCP server gives Claude access to finance news from major sources including:
- Bloomberg
- Wall Street Journal (WSJ)
- CNBC
- Seeking Alpha
- MarketWatch
- Financial Times

The server provides three tools:
1. **get_latest_finance_news** - Fetch the latest news from all sources or a specific source
2. **search_finance_news** - Search across all feeds for articles matching a keyword
3. **get_seekingalpha_ticker_thesis** - Gather a ticker's latest Seeking Alpha analysis articles to build a Buy/Hold/Sell view

## Installation

Install dependencies using uv:

```bash
uv sync
```

## How to Run

Start the MCP server:

```bash
uv run python main.py
```

Or configure it in your Claude Desktop app by adding to your MCP settings:

```json
{
  "mcpServers": {
    "finance-news": {
      "command": "uv",
      "args": ["--directory", "/path/to/example", "run", "python", "main.py"]
    }
  }
}
```

**Important Notes:**
- Replace `/path/to/example` with the actual path to your project directory
- If you get a "spawn uv ENOENT" error, use the full path to `uv`:
  - Find it with: `which uv`
  - Common locations: `~/.local/bin/uv` or `~/.cargo/bin/uv`
  - Update `command` to the full path, e.g., `"/Users/yourname/.local/bin/uv"`

## Example Questions to Ask Claude

Once connected, you can ask Claude questions like:

- "What are the latest finance news headlines?"
- "Get me the top 5 news articles from Bloomberg"
- "Search for news about 'inflation' in finance feeds"
- "What's the latest news from CNBC?"
- "Find articles about 'Federal Reserve' or 'interest rates'"
- "Show me recent Yahoo Finance headlines"

## Available Tools

### get_latest_finance_news

Fetch the latest finance news articles.

**Parameters:**
- `limit` (int, default=10): Maximum number of articles to return
- `source` (str, default="all"): News source to fetch from
  - Options: "all", "bloomberg", "wsj", "cnbc", "seekingalpha", "marketwatch", "ft"

**Example:**
```python
get_latest_finance_news(limit=5, source="wsj")
```

### search_finance_news

Search for articles matching a keyword across all feeds.

**Parameters:**
- `query` (str, required): Search keyword to find in titles or descriptions
- `limit` (int, default=10): Maximum number of matching articles to return

**Example:**
```python
search_finance_news(query="bitcoin", limit=5)
```

### get_seekingalpha_ticker_thesis

Collect a ticker's latest Seeking Alpha analysis articles (up to 10) so Claude can write the core elements of a Buy/Strong Buy, Hold and Sell/Strong Sell thesis.

**Parameters:**
- `ticker` (str, required): Stock symbol, e.g. `AAPL` (page: `https://seekingalpha.com/symbol/<ticker>`)
- `limit` (int, default=10): Articles to use, 1-10

**Returns:** `articles` (title, author, published, url, summary, rating_cue), a bullish/neutral/bearish `stance_tally`, `warnings`, and `instructions` for writing the thesis. `rating_cue` is a keyword heuristic, not a Seeking Alpha rating.

**Data providers:** Seeking Alpha blocks scraping of its ticker pages, article pages and JSON API with a captcha, so this tool does not scrape them.
- Default: the public feed `https://seekingalpha.com/api/sa/combined/<ticker>.xml`. No key needed, but it gives titles only, and few items are analysis articles.
- With `SA_RAPIDAPI_KEY` set: a licensed Seeking Alpha API on RapidAPI (host override: `SA_RAPIDAPI_HOST`), which adds article summaries. This path has not been tested against a live key.

```json
"env": { "SA_RAPIDAPI_KEY": "your-key" }
```

Output is a summary of third-party opinion, not investment advice.

## Implementation Details

- **No caching**: Fetches RSS feeds on-demand for real-time updates
- **Error handling**: Gracefully skips feeds that fail to load
- **Simple & clean**: Single-file implementation, perfect portfolio piece
- **Dependencies**: fastmcp, feedparser, httpx

## Project Structure

```
example/
├── main.py             # MCP server implementation
├── seekingalpha.py     # Seeking Alpha ticker providers and parsing
├── tests/              # pytest tests
├── pyproject.toml      # Project dependencies
├── uv.lock             # Dependency lock file
└── README.md           # This file
```

## How It Works

The server uses:
- **FastMCP** to create the MCP server and register tools
- **httpx** to fetch RSS feed URLs
- **feedparser** to parse RSS/Atom feeds into structured data

Each tool fetches feeds in real-time, parses them, and returns structured article data including title, link, published date, description, and source name.

## License

MIT
