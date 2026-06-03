# tests/test_news_report.py
import news_report


def test_format_coin_news_with_items():
    items = [
        {"title": "Bitcoin surges", "link": "https://x.test/a", "published": "2024-10-02", "source": "S"},
        {"title": "Bitcoin dips on hack", "link": "https://x.test/b", "published": "2024-10-01", "source": "S"},
    ]
    summary = {"bullish": 1, "bearish": 1, "neutral": 0, "overall": "neutral"}
    out = news_report.format_coin_news("bitcoin", items, summary, limit=5)
    assert "bitcoin" in out
    assert "neutral" in out                 # overall label
    assert "Bitcoin surges" in out
    assert "https://x.test/a" in out
    assert "2024-10-02" in out


def test_format_coin_news_respects_limit():
    items = [{"title": f"news {i}", "link": "u", "published": "2024-10-0%d" % (i + 1),
              "source": "S"} for i in range(5)]
    summary = {"bullish": 0, "bearish": 0, "neutral": 5, "overall": "neutral"}
    out = news_report.format_coin_news("bitcoin", items, summary, limit=2)
    assert "news 0" in out and "news 1" in out
    assert "news 4" not in out              # capped at 2


def test_format_coin_news_no_items():
    summary = {"bullish": 0, "bearish": 0, "neutral": 0, "overall": "neutral"}
    out = news_report.format_coin_news("bitcoin", [], summary, limit=5)
    assert "bitcoin" in out
    assert "no recent news" in out.lower()
