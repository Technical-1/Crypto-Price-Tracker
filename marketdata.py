# marketdata.py
from datetime import datetime, timezone

import requests

HISTORY_URL = (
    "https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
    "?vs_currency=usd&days={days}&interval=daily"
)
MARKETCAP_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids={ids}&vs_currencies=usd&include_market_cap=true"
)


def fetch_history(coin, days=90, timeout=10):
    """Fetch daily USD prices for one coin as a list of (YYYY-MM-DD, price).
    Raises requests.RequestException on network/HTTP failure."""
    url = HISTORY_URL.format(coin=coin, days=days)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    points = response.json().get("prices", [])
    series = []
    for ms_ts, price in points:
        day = datetime.fromtimestamp(ms_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        series.append((day, price))
    return series


def fetch_market_caps(ids, timeout=10):
    """Fetch USD market caps for the given coin ids as {coin: market_cap}.
    Raises requests.RequestException on network/HTTP failure."""
    url = MARKETCAP_URL.format(ids="%2C".join(ids))
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    caps = {}
    for coin, fields in data.items():
        cap = fields.get("usd_market_cap")
        if cap is not None:
            caps[coin] = cap
    return caps
