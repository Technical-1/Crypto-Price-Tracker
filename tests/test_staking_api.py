# tests/test_staking_api.py
from unittest.mock import Mock, patch
import staking_api


def _resp(payload):
    fake = Mock()
    fake.raise_for_status.return_value = None
    fake.json.return_value = payload
    return fake


def test_fetch_apys_matches_symbol_and_picks_highest_tvl():
    payload = {"data": [
        {"symbol": "ETH", "apy": 3.0, "tvlUsd": 100.0},
        {"symbol": "ETH", "apy": 5.0, "tvlUsd": 900.0},   # higher TVL -> chosen
        {"symbol": "XLM", "apy": 2.0, "tvlUsd": 50.0},
        {"symbol": "OTHER", "apy": 9.0, "tvlUsd": 999.0},
    ]}
    with patch("staking_api.requests.get", return_value=_resp(payload)):
        apys = staking_api.fetch_apys(["ETH", "XLM"], timeout=10)
    assert apys["ETH"] == 0.05      # 5.0 percent -> 0.05 fraction, highest TVL
    assert apys["XLM"] == 0.02
    assert "OTHER" not in apys


def test_fetch_apys_omits_unmatched_symbol():
    payload = {"data": [{"symbol": "ETH", "apy": 3.0, "tvlUsd": 100.0}]}
    with patch("staking_api.requests.get", return_value=_resp(payload)):
        apys = staking_api.fetch_apys(["ETH", "DOGE"], timeout=10)
    assert "DOGE" not in apys


def test_fetch_apys_propagates_http_error():
    import requests
    import pytest
    fake = Mock()
    fake.raise_for_status.side_effect = requests.HTTPError("503")
    with patch("staking_api.requests.get", return_value=fake):
        with pytest.raises(requests.HTTPError):
            staking_api.fetch_apys(["ETH"])
