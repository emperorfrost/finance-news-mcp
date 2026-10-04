from seekingalpha import (build_thesis_inputs, detect_rating, parse_rapidapi_details,
                          parse_rapidapi_list, parse_rss, tally_stances, validate_ticker)

RSS = """<?xml version="1.0"?><rss xmlns:sa="https://seekingalpha.com/api/1.0" version="2.0"><channel>
<item><title>Market news item</title><link>https://seekingalpha.com/symbol/AAPL/news?source=x</link></item>
<item><title>Apple: Why I'm Betting Against This Company (Rating Downgrade)</title>
<link>https://seekingalpha.com/article/1-apple?source=feed_symbol_AAPL</link>
<pubDate>Fri, 25 Sep 2026 10:01:41 -0400</pubDate><sa:author_name>Jo</sa:author_name></item>
</channel></rss>"""


def test_validate_ticker():
    assert validate_ticker(" aapl ") == "AAPL"
    assert validate_ticker("BRK.B") == "BRK.B"
    assert validate_ticker("../etc") is None
    assert validate_ticker("") is None


def test_detect_rating():
    assert detect_rating("Rating: Strong Buy") == "strong_buy"
    assert detect_rating("Apple (Rating Downgrade)") == "sell"
    assert detect_rating("Why I'm holding") is None
    assert detect_rating("Time to hold") == "hold"


def test_parse_rss_skips_news_and_strips_tracking():
    arts = parse_rss(RSS, "AAPL", 10)
    assert len(arts) == 1
    assert arts[0]["url"] == "https://seekingalpha.com/article/1-apple"
    assert arts[0]["rating_cue"] == "sell"


def test_rapidapi_parsing():
    payload = {"data": [{"id": "9", "attributes": {"title": "X: Strong Buy", "publishOn": "d"},
                         "links": {"self": "/article/9-x"},
                         "relationships": {"author": {"data": {"id": "a1"}}}}],
               "included": [{"id": "a1", "type": "author", "attributes": {"nick": "Nick"}}]}
    arts = parse_rapidapi_list(payload, 10)
    assert arts[0]["author"] == "Nick" and arts[0]["rating_cue"] == "strong_buy"
    assert parse_rapidapi_details({"data": {"attributes": {"summary": ["a", "b"]}}}) == "a b"
    assert tally_stances(arts)["bullish"] == 1


def test_invalid_ticker_returns_error():
    assert "error" in build_thesis_inputs("not a ticker!")
