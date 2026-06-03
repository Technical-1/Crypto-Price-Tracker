import history
from ledger import Transaction


def test_holdings_as_of_excludes_later_transactions():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-03-01", "bitcoin", "buy", 1.0, 200.0, 0.0),  # after cutoff
    ]
    held = history.holdings_as_of(txns, "2024-02-01")
    assert held["bitcoin"]["total"] == 1.0
    assert held["bitcoin"]["cost"] == 100.0


def test_holdings_as_of_includes_cutoff_date():
    txns = [Transaction("2024-02-01", "bitcoin", "buy", 2.0, 100.0, 0.0)]
    held = history.holdings_as_of(txns, "2024-02-01")
    assert held["bitcoin"]["total"] == 2.0


def test_holdings_as_of_before_any_txn_is_empty():
    txns = [Transaction("2024-02-01", "bitcoin", "buy", 2.0, 100.0, 0.0)]
    assert history.holdings_as_of(txns, "2024-01-01") == {}


def test_reconstruct_series_values_holdings_per_day():
    txns = [Transaction("2024-01-01", "bitcoin", "buy", 2.0, 100.0, 0.0)]  # cost 200, 100/unit
    prices = {"bitcoin": {"2024-01-01": 100.0, "2024-01-02": 150.0}}
    series = history.reconstruct_series(txns, prices, ["2024-01-01", "2024-01-02"])
    assert series[0] == {"date": "2024-01-01", "value": 200.0, "cost": 200.0, "pl": 0.0}
    assert series[1] == {"date": "2024-01-02", "value": 300.0, "cost": 200.0, "pl": 100.0}


def test_reconstruct_series_skips_coin_without_price_that_day():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-01-01", "ethereum", "buy", 10.0, 10.0, 0.0),  # cost 100
    ]
    # ethereum has no price on 2024-01-02 -> excluded that day (value + cost)
    prices = {
        "bitcoin": {"2024-01-01": 100.0, "2024-01-02": 120.0},
        "ethereum": {"2024-01-01": 10.0},
    }
    series = history.reconstruct_series(txns, prices, ["2024-01-01", "2024-01-02"])
    assert series[0]["value"] == 200.0   # 100 + 100
    assert series[0]["cost"] == 200.0
    assert series[1]["value"] == 120.0   # only bitcoin
    assert series[1]["cost"] == 100.0    # only bitcoin's basis counted


def test_reconstruct_series_empty_dates_is_empty():
    assert history.reconstruct_series([], {}, []) == []
