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


def test_compute_profit_single_coin():
    # avg cost = 200/1 = 200; price 300 -> profit 100
    assert cpt.compute_profit({"total": 1, "cost": 200}, 300) == 100


def test_compute_profit_multiple_coins():
    # avg cost = 200/2 = 100; price 150 -> per-coin 50 * 2 = 100
    assert cpt.compute_profit({"total": 2, "cost": 200}, 150) == 100


def test_compute_profit_zero_total_returns_none():
    assert cpt.compute_profit({"total": 0, "cost": 20}, 50) is None


def test_compute_profit_negative_total_returns_none():
    assert cpt.compute_profit({"total": -1, "cost": 20}, 50) is None


def test_main_skips_missing_coin_and_prints_present_one(capsys):
    holdings = {
        "bitcoin": {"total": 1, "cost": 200},
        "mirror-protocol": {"total": 1, "cost": 20},  # absent from payload
    }
    payload = {"bitcoin": {"usd": 50000, "usd_24h_change": 1.5}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=payload):
        cpt.main(holdings=holdings)
    captured = capsys.readouterr()
    assert "Coin" in captured.out             # table header still printed
    assert "bitcoin" in captured.out          # present coin -> stdout table
    assert "mirror-protocol" not in captured.out  # missing coin not in table
    assert "mirror-protocol" in captured.err  # skip notice on stderr


def test_main_skips_zero_total_holding(capsys):
    holdings = {"bitcoin": {"total": 0, "cost": 200}}
    payload = {"bitcoin": {"usd": 50000, "usd_24h_change": 1.5}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=payload):
        cpt.main(holdings=holdings)
    captured = capsys.readouterr()
    assert "bitcoin" not in captured.out      # not in the table
    assert "bitcoin" in captured.err          # skip notice on stderr


def test_main_skips_coin_present_but_missing_usd_key(capsys):
    holdings = {"bitcoin": {"total": 1, "cost": 200}}
    payload = {"bitcoin": {"usd_24h_change": 1.5}}  # 'usd' key absent
    with patch("CryptoPriceTracker.fetch_prices", return_value=payload):
        cpt.main(holdings=holdings)
    captured = capsys.readouterr()
    assert "bitcoin" not in captured.out
    assert "bitcoin" in captured.err


def test_main_skips_coin_with_null_usd_price(capsys):
    holdings = {"bitcoin": {"total": 1, "cost": 200}}
    payload = {"bitcoin": {"usd": None, "usd_24h_change": 1.5}}  # 'usd' is None
    with patch("CryptoPriceTracker.fetch_prices", return_value=payload):
        cpt.main(holdings=holdings)
    captured = capsys.readouterr()
    assert "bitcoin" not in captured.out
    assert "bitcoin" in captured.err


def test_main_handles_fractional_cost(capsys):
    holdings = {"bitcoin": {"total": 1, "cost": 19.99}}
    payload = {"bitcoin": {"usd": 50000, "usd_24h_change": 1.5}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=payload):
        cpt.main(holdings=holdings)
    captured = capsys.readouterr()
    assert "bitcoin" in captured.out      # row printed, no crash
    assert "19.99" in captured.out        # fractional cost rendered
    assert "bitcoin" not in captured.err  # not skipped
