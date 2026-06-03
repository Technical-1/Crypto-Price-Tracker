from unittest.mock import Mock, patch

import pytest
import requests

import CryptoPriceTracker as cpt


def test_fetch_prices_returns_parsed_json_and_passes_timeout():
    fake = Mock()
    fake.raise_for_status.return_value = None
    fake.json.return_value = {"bitcoin": {"usd": 50000, "usd_24h_change": 1.5}}
    with patch("CryptoPriceTracker.requests.get", return_value=fake) as mock_get:
        data = cpt.fetch_prices("http://example.test", timeout=10)
    assert data == {"bitcoin": {"usd": 50000, "usd_24h_change": 1.5}}
    mock_get.assert_called_once_with("http://example.test", timeout=10)
    fake.raise_for_status.assert_called_once()


def test_fetch_prices_propagates_http_error():
    fake = Mock()
    fake.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")
    with patch("CryptoPriceTracker.requests.get", return_value=fake):
        with pytest.raises(requests.HTTPError):
            cpt.fetch_prices("http://example.test")


def test_main_exits_1_on_network_error(capsys):
    with patch("CryptoPriceTracker.fetch_prices",
               side_effect=requests.ConnectionError("network down")):
        with pytest.raises(SystemExit) as exc:
            cpt.main(holdings={"bitcoin": {"total": 1, "cost": 200}})
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Failed to fetch prices" in err
