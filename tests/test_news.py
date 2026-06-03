# tests/test_news.py
import json
import news


def test_load_news_config_valid(tmp_path):
    path = tmp_path / "news.json"
    path.write_text(json.dumps({
        "feeds": ["https://x.test/rss"], "cryptopanic_token": "tok",
        "keywords": {"bitcoin": ["bitcoin", "btc"]},
    }))
    cfg = news.load_news_config(str(path))
    assert cfg["feeds"] == ["https://x.test/rss"]
    assert cfg["cryptopanic_token"] == "tok"
    assert cfg["keywords"]["bitcoin"] == ["bitcoin", "btc"]


def test_load_news_config_missing_uses_defaults(tmp_path):
    cfg = news.load_news_config(str(tmp_path / "nope.json"))
    assert cfg["feeds"]                     # non-empty default feeds
    assert cfg["cryptopanic_token"] == ""
    assert cfg["keywords"] == {}


def test_load_news_config_malformed_uses_defaults(tmp_path, capsys):
    path = tmp_path / "news.json"
    path.write_text("{bad json")
    cfg = news.load_news_config(str(path))
    assert cfg["feeds"]
    assert "default" in capsys.readouterr().err.lower()


def test_keywords_for_defaults_to_coin_id():
    assert news.keywords_for("bitcoin", {"keywords": {}}) == ["bitcoin"]
    assert news.keywords_for("bitcoin", {"keywords": {"bitcoin": ["btc", "bitcoin"]}}) == ["btc", "bitcoin"]


def test_filter_items_whole_word_case_insensitive():
    items = [
        {"title": "Bitcoin surges", "link": "", "published": "", "source": ""},
        {"title": "theos protocol news", "link": "", "published": "", "source": ""},  # not 'eos'
        {"title": "EOS mainnet update", "link": "", "published": "", "source": ""},
    ]
    btc = news.filter_items(items, ["bitcoin"])
    assert len(btc) == 1 and btc[0]["title"] == "Bitcoin surges"
    eos = news.filter_items(items, ["eos"])
    assert len(eos) == 1 and eos[0]["title"] == "EOS mainnet update"  # 'theos' excluded


def test_classify_sentiment_bullish_bearish_neutral():
    assert news.classify_sentiment("Bitcoin surges to record rally") == "bullish"
    assert news.classify_sentiment("Market crashes amid hack and lawsuit") == "bearish"
    assert news.classify_sentiment("Company announces quarterly report") == "neutral"
    assert news.classify_sentiment("rally crash") == "neutral"  # tie


def test_sentiment_summary_tally_and_overall():
    items = [
        {"title": "Bitcoin surges and rallies", "link": "", "published": "", "source": ""},
        {"title": "Bitcoin gains adoption", "link": "", "published": "", "source": ""},
        {"title": "Bitcoin crashes after hack", "link": "", "published": "", "source": ""},
    ]
    summary = news.sentiment_summary(items)
    assert summary["bullish"] == 2
    assert summary["bearish"] == 1
    assert summary["neutral"] == 0
    assert summary["overall"] == "bullish"
