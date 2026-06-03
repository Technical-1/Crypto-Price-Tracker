# tests/test_holdings.py
import holdings
from ledger import Transaction


def test_derive_holdings_from_remaining_lots():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 2.0, 100.0, 0.0),   # 200 basis
        Transaction("2024-02-01", "bitcoin", "sell", 1.0, 150.0, 0.0),  # 1 left, 100 basis
        Transaction("2024-01-01", "ethereum", "buy", 5.0, 10.0, 0.0),   # 50 basis
    ]
    result = holdings.derive_holdings(txns, method="fifo")
    assert result["bitcoin"] == {"total": 1.0, "cost": 100.0}
    assert result["ethereum"] == {"total": 5.0, "cost": 50.0}


def test_derive_holdings_omits_fully_sold_coin():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-02-01", "bitcoin", "sell", 1.0, 150.0, 0.0),
    ]
    assert "bitcoin" not in holdings.derive_holdings(txns, method="fifo")


def test_load_holdings_or_default_falls_back(tmp_path):
    fallback = {"bitcoin": {"total": 1, "cost": 200}}
    result = holdings.load_holdings_or_default(
        str(tmp_path / "missing.json"), fallback=fallback)
    assert result == fallback


def test_load_holdings_or_default_uses_ledger_when_present(tmp_path):
    import ledger
    path = tmp_path / "ledger.json"
    ledger.save_ledger(str(path), [Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0)])
    result = holdings.load_holdings_or_default(str(path), fallback={"x": {"total": 1, "cost": 1}})
    assert result == {"bitcoin": {"total": 1.0, "cost": 100.0}}
