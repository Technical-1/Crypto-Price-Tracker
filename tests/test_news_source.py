# tests/test_news_source.py
from unittest.mock import Mock, patch
import news_source


SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Sample Crypto News</title>
<item><title>Bitcoin surges to record high</title>
<link>https://example.test/a</link>
<pubDate>Wed, 02 Oct 2024 13:00:00 GMT</pubDate></item>
<item><title>Ethereum upgrade ships</title>
<link>https://example.test/b</link>
<pubDate>not a date</pubDate></item>
</channel></rss>"""


def _resp(text):
    fake = Mock()
    fake.raise_for_status.return_value = None
    fake.text = text
    return fake


def test_fetch_rss_parses_items_and_dates():
    with patch("news_source.requests.get", return_value=_resp(SAMPLE_RSS)):
        items = news_source.fetch_rss("https://example.test/rss", timeout=10)
    assert len(items) == 2
    assert items[0]["title"] == "Bitcoin surges to record high"
    assert items[0]["link"] == "https://example.test/a"
    assert items[0]["published"] == "2024-10-02"
    assert items[0]["source"] == "Sample Crypto News"
    assert items[1]["published"] == ""   # unparseable date -> ""


def test_fetch_rss_propagates_http_error():
    import requests
    import pytest
    fake = Mock()
    fake.raise_for_status.side_effect = requests.HTTPError("500")
    with patch("news_source.requests.get", return_value=fake):
        with pytest.raises(requests.HTTPError):
            news_source.fetch_rss("https://example.test/rss")


def test_fetch_rss_rejects_doctype_entity_bomb():
    # A DTD with custom entities is the vector for billion-laughs / XXE. RSS feeds
    # never need a DOCTYPE, so refuse to parse one.
    import pytest
    malicious = ('<?xml version="1.0"?>\n'
                 '<!DOCTYPE lolz [<!ENTITY lol "lol">]>\n'
                 '<rss><channel><title>x</title></channel></rss>')
    with patch("news_source.requests.get", return_value=_resp(malicious)):
        with pytest.raises(ValueError, match="DOCTYPE"):
            news_source.fetch_rss("https://example.test/rss")


def test_fetch_cryptopanic_parses_results():
    payload = {"results": [
        {"title": "BTC rallies", "url": "https://cp.test/1", "published_at": "2024-10-02T13:00:00Z"},
        {"title": "ETH dips", "url": "https://cp.test/2", "published_at": "2024-10-01T08:00:00Z"},
    ]}
    fake = Mock()
    fake.raise_for_status.return_value = None
    fake.json.return_value = payload
    with patch("news_source.requests.get", return_value=fake) as mock_get:
        items = news_source.fetch_cryptopanic("tok", ["BTC", "ETH"], timeout=10)
    assert items[0] == {"title": "BTC rallies", "link": "https://cp.test/1",
                        "published": "2024-10-02", "source": "CryptoPanic"}
    assert items[1]["published"] == "2024-10-01"
    url = mock_get.call_args[0][0]
    assert "auth_token=tok" in url and "BTC" in url


def test_fetch_cryptopanic_propagates_http_error():
    import requests
    import pytest
    fake = Mock()
    fake.raise_for_status.side_effect = requests.HTTPError("403")
    with patch("news_source.requests.get", return_value=fake):
        with pytest.raises(requests.HTTPError):
            news_source.fetch_cryptopanic("tok", ["BTC"])
