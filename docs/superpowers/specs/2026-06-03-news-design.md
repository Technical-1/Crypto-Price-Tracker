# News & Sentiment Feed — Design Spec

**Issue:** #4 — Add News & Sentiment Feed for Tracked Coins
**Date:** 2026-06-03
**Author:** Jacob Kanfer

## Context

`Crypto-Price-Tracker` is a dependency-light Python CLI. Issues #1–#3 added a
ledger/holdings model (`holdings.py`), resilient fetching, and several
subcommands. This feature shows recent news per tracked coin with a naive
bullish/bearish sentiment tag. It stays CLI-native and dependency-light
(`requests` + stdlib only: `xml.etree`, `email.utils`, `json`).

Decisions locked in during brainstorming:

- **News source:** keyless RSS feeds by default (stdlib XML parsing), with an
  optional CryptoPanic API path if a token is configured.
- **Sentiment:** a naive keyword-lexicon classifier over headlines
  (bullish/bearish/neutral), working for either source. Explicitly a heuristic,
  not ML.
- **Click-through:** print the article URL (terminals make it clickable); no
  browser launching.

## Goals

1. Fetch recent crypto news, per tracked coin, from keyless RSS feeds (default)
   or CryptoPanic (optional, token-based).
2. Filter items to each coin by configurable keywords (whole-word match).
3. Tag each headline bullish/bearish/neutral via a keyword lexicon, and show a
   per-coin sentiment summary.
4. Print dated headlines with their article URLs for click-through.

## Non-Goals

- ML / model-based sentiment analysis.
- Social-media (Twitter/Reddit) scraping.
- A web/GUI frontend, charts, or graph annotations (issue #5 may later overlay
  the dated items).
- Launching a browser.

## Architecture

New stdlib-only modules; reuses `holdings.py`. `requests` remains the only pip
dependency.

```
news_source.py   # fetch_rss(url, timeout) -> items; DEFAULT_FEEDS;
                 #   fetch_cryptopanic(token, currencies, timeout) -> items (optional)
news.py          # load_news_config, keywords_for, filter_items, classify_sentiment,
                 #   sentiment_summary  (pure logic)
news_report.py   # format_coin_news(coin, items, summary, limit) -> string
CryptoPriceTracker.py  # new `news [--coin ID] [--limit 5]` subcommand
news.sample.json       # committed sample config (user's news.json is gitignored)
```

## Data Model

A news **item** is a dict: `{"title": str, "link": str, "published": str
(YYYY-MM-DD or ""), "source": str}`.

### news.json (all fields optional)

```json
{
  "feeds": ["https://cointelegraph.com/rss"],
  "cryptopanic_token": "",
  "keywords": {"bitcoin": ["bitcoin", "btc"], "ethereum": ["ethereum", "eth"]}
}
```

- `feeds`: RSS feed URLs; missing → built-in `DEFAULT_FEEDS`.
- `cryptopanic_token`: enables the CryptoPanic path when non-empty.
- `keywords`: per-coin match keywords; a coin absent here defaults to `[coin_id]`.

## Components

### news_source.py (network)

- `DEFAULT_FEEDS` — a small built-in list of keyless crypto-news RSS URLs.
- `fetch_rss(url, timeout=10)` → `list[item]`. GET the feed, `raise_for_status()`,
  parse with `xml.etree.ElementTree`: each `channel/item` yields `title`, `link`,
  and `pubDate` (parsed via `email.utils.parsedate_to_datetime` to a `YYYY-MM-DD`
  string; unparseable → `""`). `source` is the feed's `channel/title` or the URL
  host. Raises `requests.RequestException` on network/HTTP failure.
- `fetch_cryptopanic(token, currencies, timeout=10)` → `list[item]`. GET
  `https://cryptopanic.com/api/v1/posts/?auth_token={token}&currencies={CSV}`,
  map `results[].title`/`.url`/`.published_at` (date prefix) into items. Raises
  `requests.RequestException` on failure.

### news.py (pure logic)

- `load_news_config(path)` → dict with keys `feeds`, `cryptopanic_token`,
  `keywords`. Missing file → defaults (`DEFAULT_FEEDS`, `""`, `{}`) silently;
  malformed JSON → defaults with a stderr warning.
- `keywords_for(coin, config)` → the configured keyword list for the coin, else
  `[coin]`.
- `filter_items(items, keywords)` → items whose `title` contains any keyword as a
  whole word, case-insensitive (regex word boundaries so "eos" does not match
  "theos").
- `BULLISH` / `BEARISH` — lexicon sets. `classify_sentiment(text)` → counts
  whole-word lexicon hits; more bullish → `"bullish"`, more bearish →
  `"bearish"`, tie or none → `"neutral"`.
- `sentiment_summary(items)` → `{"bullish": n, "bearish": n, "neutral": n,
  "overall": label}` where overall is the majority tag (tie → "neutral").

### news_report.py (return strings, no I/O)

- `format_coin_news(coin, items, summary, limit)` → a header line with the coin
  and its sentiment summary (`bitcoin — bullish (3 up / 1 down / 1 neutral)`),
  then up to `limit` lines of `date  [sentiment]  title` followed by the URL, or
  a `(no recent news)` line when `items` is empty.

## CLI Surface

```
python3 CryptoPriceTracker.py news [--coin ID] [--limit 5]
```

The command:

1. Loads `news.json` (or defaults).
2. Determines coins: `--coin` if given, else held coins from the ledger
   (`holdings.load_holdings_or_default(LEDGER_PATH, originalHoldings)`).
3. If a `cryptopanic_token` is set, fetches CryptoPanic items for all coin
   symbols/ids once; on failure falls back to RSS.
4. Fetches each RSS feed once (skipping failures with a notice), pooling items.
5. Per coin: filters by keywords, classifies sentiment, prints the section
   (headlines capped at `--limit`, newest first by `published`).

The default (no-arg) behavior and other subcommands are unchanged.

## Error Handling

- A feed that fails to fetch or parse → stderr notice; continue with the others.
- CryptoPanic configured but failing → stderr notice; fall back to RSS only.
- Missing `news.json` → built-in defaults (silent). Malformed `news.json` →
  defaults with a stderr warning.
- No coins to cover (empty holdings and no `--coin`) → clear message, exit 1.
- All sources fail (no items from anywhere) → a readable message; exit 1.

## Testing

`pytest`, no network (mock `fetch_rss` / `requests`). Coverage:

- `fetch_rss`: parse a sample RSS XML string into items; RFC-822 `pubDate` →
  `YYYY-MM-DD`; unparseable date → `""`; HTTP error propagates.
- `classify_sentiment`: bullish phrase → "bullish"; bearish → "bearish"; mixed
  tie / none → "neutral".
- `filter_items`: whole-word match; no false substring match ("eos" not in
  "theos"); case-insensitive.
- `sentiment_summary`: correct tally and overall label.
- `load_news_config`: valid; missing → defaults; malformed → defaults + warning.
- `fetch_cryptopanic`: parse a mocked payload into items; HTTP error propagates.
- `format_coin_news`: headers, capped headline count, "(no recent news)".
- CLI: news prints per-coin sections; feed-failure skip; empty-coins exit 1.
- Existing suite stays green.

## Out of Scope / Future

News items carry dates so issue #5 (historical playback) can later overlay
"major news" markers. No graphing here.
