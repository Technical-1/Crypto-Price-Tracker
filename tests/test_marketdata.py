# tests/test_marketdata.py
from unittest.mock import Mock, patch
import marketdata


def test_fetch_history_reduces_to_daily_date_price():
    fake = Mock()
    fake.raise_for_status.return_value = None
    # CoinGecko market_chart: prices = [[ms_ts, price], ...]
    fake.json.return_value = {"prices": [
        [1704067200000, 100.0],  # 2024-01-01
        [1704153600000, 110.0],  # 2024-01-02
    ]}
    with patch("marketdata.requests.get", return_value=fake) as mock_get:
        series = marketdata.fetch_history("bitcoin", days=2, timeout=10)
    assert series == [("2024-01-01", 100.0), ("2024-01-02", 110.0)]
    assert mock_get.call_count == 1
    # the URL should reference the coin id and days
    called_url = mock_get.call_args[0][0]
    assert "bitcoin" in called_url and "days=2" in called_url


def test_fetch_market_caps_parses_usd_market_cap():
    fake = Mock()
    fake.raise_for_status.return_value = None
    fake.json.return_value = {
        "bitcoin": {"usd": 50000, "usd_market_cap": 1.0e12},
        "ethereum": {"usd": 3000, "usd_market_cap": 4.0e11},
    }
    with patch("marketdata.requests.get", return_value=fake):
        caps = marketdata.fetch_market_caps(["bitcoin", "ethereum"])
    assert caps == {"bitcoin": 1.0e12, "ethereum": 4.0e11}


def test_fetch_history_propagates_http_error():
    import requests
    fake = Mock()
    fake.raise_for_status.side_effect = requests.HTTPError("429")
    with patch("marketdata.requests.get", return_value=fake):
        import pytest
        with pytest.raises(requests.HTTPError):
            marketdata.fetch_history("bitcoin", days=2)
