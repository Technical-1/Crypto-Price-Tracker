import pytest
import ledger


def test_validate_row_builds_transaction():
    txn = ledger.validate_row({
        "date": "2024-01-15", "coin": "bitcoin", "action": "buy",
        "quantity": "0.5", "price_usd": "40000", "fee_usd": "10",
    })
    assert txn == ledger.Transaction("2024-01-15", "bitcoin", "buy", 0.5, 40000.0, 10.0)


def test_validate_row_rejects_bad_action():
    with pytest.raises(ValueError, match="action"):
        ledger.validate_row({
            "date": "2024-01-15", "coin": "bitcoin", "action": "trade",
            "quantity": "1", "price_usd": "1", "fee_usd": "0",
        })


def test_validate_row_rejects_nonpositive_quantity():
    with pytest.raises(ValueError, match="quantity"):
        ledger.validate_row({
            "date": "2024-01-15", "coin": "bitcoin", "action": "buy",
            "quantity": "0", "price_usd": "1", "fee_usd": "0",
        })


def test_validate_row_rejects_bad_date():
    with pytest.raises(ValueError, match="date"):
        ledger.validate_row({
            "date": "15-01-2024", "coin": "bitcoin", "action": "buy",
            "quantity": "1", "price_usd": "1", "fee_usd": "0",
        })


def test_save_then_load_roundtrips(tmp_path):
    path = tmp_path / "ledger.json"
    txns = [
        ledger.Transaction("2024-01-15", "bitcoin", "buy", 0.5, 40000.0, 10.0),
        ledger.Transaction("2024-06-01", "bitcoin", "sell", 0.2, 60000.0, 5.0),
    ]
    ledger.save_ledger(str(path), txns)
    loaded = ledger.load_ledger(str(path))
    assert loaded == txns


def test_load_missing_file_returns_empty(tmp_path):
    assert ledger.load_ledger(str(tmp_path / "nope.json")) == []
