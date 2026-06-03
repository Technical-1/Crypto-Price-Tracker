# news.py
import json
import re
import sys

import news_source

BULLISH = {"surge", "surges", "rally", "rallies", "soar", "soars", "gains", "gain",
           "bullish", "jumps", "climbs", "record", "adoption", "breakout", "upgrade",
           "high", "rises", "boom", "approval"}
BEARISH = {"crash", "crashes", "plunge", "plunges", "drop", "drops", "falls", "fall",
           "bearish", "hack", "hacked", "lawsuit", "ban", "selloff", "decline",
           "dump", "exploit", "low", "slumps", "fraud", "fear"}


def load_news_config(path):
    """Load news config. Missing file -> defaults silently; malformed -> defaults
    with a stderr warning. Always returns keys feeds/cryptopanic_token/keywords."""
    defaults = {"feeds": list(news_source.DEFAULT_FEEDS), "cryptopanic_token": "", "keywords": {}}
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return defaults
    except json.JSONDecodeError as err:
        print(f"Warning: using default news config ({err})", file=sys.stderr)
        return defaults
    return {
        "feeds": data.get("feeds") or list(news_source.DEFAULT_FEEDS),
        "cryptopanic_token": data.get("cryptopanic_token", ""),
        "keywords": data.get("keywords", {}),
    }


def keywords_for(coin, config):
    """Return the configured match keywords for a coin, or [coin] by default."""
    return config.get("keywords", {}).get(coin, [coin])


def _has_word(text, word):
    return re.search(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE) is not None


def filter_items(items, keywords):
    """Return items whose title contains any keyword as a whole word (case-insensitive)."""
    return [it for it in items if any(_has_word(it["title"], k) for k in keywords)]


def classify_sentiment(text):
    """Naive lexicon sentiment: 'bullish', 'bearish', or 'neutral' (tie/none)."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    bull = sum(1 for w in words if w in BULLISH)
    bear = sum(1 for w in words if w in BEARISH)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def sentiment_summary(items):
    """Tally sentiment across items and pick an overall label (tie -> neutral)."""
    tally = {"bullish": 0, "bearish": 0, "neutral": 0}
    for it in items:
        tally[classify_sentiment(it["title"])] += 1
    if tally["bullish"] > tally["bearish"]:
        overall = "bullish"
    elif tally["bearish"] > tally["bullish"]:
        overall = "bearish"
    else:
        overall = "neutral"
    return {**tally, "overall": overall}
