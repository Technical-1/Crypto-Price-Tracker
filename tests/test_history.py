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
