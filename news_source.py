# news_source.py
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

DEFAULT_FEEDS = [
    "https://cointelegraph.com/rss",
]

CRYPTOPANIC_URL = (
    "https://cryptopanic.com/api/v1/posts/?auth_token={token}&currencies={currencies}"
)


def _to_date(pubdate):
    if not pubdate:
        return ""
    try:
        return parsedate_to_datetime(pubdate).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def fetch_rss(url, timeout=10):
    """Fetch and parse an RSS feed into a list of news items
    {title, link, published (YYYY-MM-DD or ''), source}. Raises
    requests.RequestException on network/HTTP failure, or ValueError if the
    document declares a DOCTYPE.

    Security: xml.etree does not resolve external entities (so XXE/SSRF is not
    exploitable), but it can be DoS'd by entity-expansion ("billion laughs"),
    which requires a DTD with custom entity definitions. RSS feeds never need a
    DOCTYPE, so we refuse to parse any document that contains one. This keeps the
    project stdlib-only (no defusedxml dependency) while closing the vector."""
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    text = response.text
    if "<!DOCTYPE" in text.upper():
        raise ValueError(f"refusing to parse feed with a DOCTYPE (possible XML entity attack): {url}")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as err:
        raise ValueError(f"malformed XML in feed {url}: {err}")
    channel = root.find("channel")
    if channel is None:
        return []
    source = (channel.findtext("title") or url).strip()
    items = []
    for item in channel.findall("item"):
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "published": _to_date(item.findtext("pubDate")),
            "source": source,
        })
    return items


def fetch_cryptopanic(token, currencies, timeout=10):
    """Fetch news from CryptoPanic for the given currency codes. Returns a list
    of items {title, link, published (YYYY-MM-DD), source}. Raises
    requests.RequestException on network/HTTP failure."""
    url = CRYPTOPANIC_URL.format(token=token, currencies="%2C".join(currencies))
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    results = response.json().get("results", [])
    items = []
    for r in results:
        published = (r.get("published_at") or "")[:10]  # 'YYYY-MM-DDTHH...' -> date
        items.append({
            "title": (r.get("title") or "").strip(),
            "link": (r.get("url") or "").strip(),
            "published": published,
            "source": "CryptoPanic",
        })
    return items
