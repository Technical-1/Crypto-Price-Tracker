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


def test_import_csv_appends_valid_skips_invalid_and_dupes(tmp_path, capsys):
    csv_path = tmp_path / "txns.csv"
    csv_path.write_text(
        "date,coin,action,quantity,price_usd,fee_usd\n"
        "2024-01-15,bitcoin,buy,0.5,40000,10\n"        # valid
        "2024-02-01,ethereum,trade,1,2000,1\n"          # invalid action -> skipped
        "2024-01-15,bitcoin,buy,0.5,40000,10\n"         # exact dupe of row 1 -> one kept
    )
    ledger_path = tmp_path / "ledger.json"
    added, skipped = ledger.import_csv(str(csv_path), str(ledger_path))
    assert added == 1
    assert skipped == 2
    loaded = ledger.load_ledger(str(ledger_path))
    assert loaded == [ledger.Transaction("2024-01-15", "bitcoin", "buy", 0.5, 40000.0, 10.0)]
    err = capsys.readouterr().err
    assert "ethereum" in err   # invalid-row notice
    assert "duplicate" in err  # duplicate-skip notice


def test_validate_row_rejects_missing_required_key():
    with pytest.raises(ValueError, match="price_usd"):
        ledger.validate_row({
            "date": "2024-01-15", "coin": "bitcoin", "action": "buy",
            "quantity": "1",
            # price_usd key intentionally omitted
        })


def test_validate_row_rejects_negative_fee():
    with pytest.raises(ValueError, match="fee_usd"):
        ledger.validate_row({
            "date": "2024-01-15", "coin": "bitcoin", "action": "buy",
            "quantity": "1", "price_usd": "100", "fee_usd": "-5",
        })


def test_add_interactive_appends_one(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    answers = iter(["2024-03-01", "ethereum", "buy", "2", "1500", "3"])
    txn = ledger.add_interactive(str(ledger_path), input_fn=lambda _prompt: next(answers))
    assert txn == ledger.Transaction("2024-03-01", "ethereum", "buy", 2.0, 1500.0, 3.0)
    assert ledger.load_ledger(str(ledger_path)) == [txn]
