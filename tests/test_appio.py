"""Minimal guard: the 13 migrated modules must not exist; the packages must import."""

import csv as _csv
import importlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import pytest

import appio
import coinbasis
import cryptolytics


def _write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


def test_migrated_modules_are_deleted():
    deleted = [
        "ledger", "costbasis", "holdings", "tax", "analytics",
        "rebalance", "backtest", "marketdata", "staking", "staking_api",
        "news", "news_source", "history",
    ]
    for name in deleted:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)


def test_packages_importable():
    import coinbasis          # noqa: F401
    import cryptolytics       # noqa: F401


def test_load_ledger_coinbasis_schema_empty(tmp_path):
    """An empty coinbasis array returns an empty list."""
    ledger_path = tmp_path / "ledger.json"
    _write_json(ledger_path, [])
    txs = appio.load_ledger(str(ledger_path))
    assert txs == []


def test_load_ledger_coinbasis_schema_buy(tmp_path):
    """A valid coinbasis Buy entry is parsed to a coinbasis.Buy."""
    ledger_path = tmp_path / "ledger.json"
    _write_json(ledger_path, [
        {"Buy": {
            "timestamp": "2024-01-01T00:00:00Z",
            "wallet": "default",
            "asset": "bitcoin",
            "quantity": "1",
            "unit_price": "50000",
            "fee": "0",
        }}
    ])
    txs = appio.load_ledger(str(ledger_path))
    assert len(txs) == 1
    tx = txs[0]
    assert isinstance(tx, coinbasis.Buy)
    assert tx.asset == "bitcoin"
    assert tx.wallet == "default"
    assert tx.quantity == Decimal("1")
    assert tx.unit_price == Decimal("50000")


def test_load_ledger_missing_file_raises(tmp_path):
    """Missing ledger exits with code 1 (FileNotFoundError converted to SystemExit)."""
    with pytest.raises(SystemExit) as exc_info:
        appio.load_ledger(str(tmp_path / "nofile.json"))
    assert exc_info.value.code == 1


def test_migrate_v1_buy_row():
    rows = [{"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
             "quantity": 1.0, "price_usd": 50000.0, "fee_usd": 10.0}]
    txs = appio.migrate_v1_ledger(rows)
    assert len(txs) == 1
    tx = txs[0]
    assert isinstance(tx, coinbasis.Buy)
    assert tx.wallet == "default"
    assert tx.asset == "bitcoin"
    assert tx.quantity == Decimal("1.0")
    assert tx.unit_price == Decimal("50000.0")
    assert tx.fee == Decimal("10.0")
    expected_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert tx.timestamp == expected_ts


def test_migrate_v1_sell_row():
    rows = [{"date": "2024-06-01", "coin": "ethereum", "action": "sell",
             "quantity": 0.5, "price_usd": 3000.0, "fee_usd": 0.0}]
    txs = appio.migrate_v1_ledger(rows)
    assert len(txs) == 1
    assert isinstance(txs[0], coinbasis.Sell)
    assert txs[0].asset == "ethereum"


def test_migrate_v1_invalid_row_skipped():
    """A row with quantity <= 0 is skipped with a stderr notice (not a crash)."""
    rows = [
        {"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
         "quantity": -1.0, "price_usd": 50000.0, "fee_usd": 0.0},
        {"date": "2024-01-02", "coin": "bitcoin", "action": "buy",
         "quantity": 1.0, "price_usd": 50000.0, "fee_usd": 0.0},
    ]
    txs = appio.migrate_v1_ledger(rows)
    assert len(txs) == 1  # bad row skipped
    assert txs[0].quantity == Decimal("1.0")


def test_v1_schema_detection():
    v1_rows = [{"date": "2024-01-01", "coin": "btc", "action": "buy",
                "quantity": 1, "price_usd": 100, "fee_usd": 0}]
    coinbasis_rows = [{"Buy": {"timestamp": "2024-01-01T00:00:00Z",
                               "wallet": "default", "asset": "btc",
                               "quantity": "1", "unit_price": "100", "fee": "0"}}]
    assert appio._is_v1_schema(v1_rows) is True
    assert appio._is_coinbasis_schema(v1_rows) is False
    assert appio._is_coinbasis_schema(coinbasis_rows) is True
    assert appio._is_v1_schema(coinbasis_rows) is False


def test_auto_migrate_rewrites_ledger_and_creates_backup(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.json"
    v1_data = [{"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
                "quantity": 1.0, "price_usd": 50000.0, "fee_usd": 0.0}]
    _write_json(ledger_path, v1_data)

    txs = appio.load_ledger(str(ledger_path))

    # Returns the converted transactions
    assert len(txs) == 1
    assert isinstance(txs[0], coinbasis.Buy)

    # Backup was created
    bak_path = str(ledger_path) + ".v1.bak"
    assert os.path.exists(bak_path)
    with open(bak_path) as f:
        bak = json.load(f)
    assert bak == v1_data  # original V1 content

    # Rewritten file is now in coinbasis schema
    with open(ledger_path) as f:
        rewritten = json.load(f)
    assert len(rewritten) == 1
    assert "Buy" in rewritten[0]

    # Stderr contains the migration notice
    err = capsys.readouterr().err
    assert "migrated" in err
    assert ".v1.bak" in err


def test_auto_migrate_does_not_overwrite_existing_backup(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.json"
    bak_path = str(ledger_path) + ".v1.bak"
    v1_data = [{"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
                "quantity": 1.0, "price_usd": 50000.0, "fee_usd": 0.0}]
    _write_json(ledger_path, v1_data)
    # Pre-existing backup with different content
    with open(bak_path, "w") as f:
        f.write("existing backup")

    appio.load_ledger(str(ledger_path))

    # Backup is not overwritten
    with open(bak_path) as f:
        assert f.read() == "existing backup"


def test_load_ledger_idempotent_after_migration(tmp_path, capsys):
    """Loading an already-migrated coinbasis ledger does not re-migrate it."""
    ledger_path = tmp_path / "ledger.json"
    v1_data = [{"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
                "quantity": 1.0, "price_usd": 50000.0, "fee_usd": 0.0}]
    _write_json(ledger_path, v1_data)

    # First load: migrates
    appio.load_ledger(str(ledger_path))
    capsys.readouterr()  # consume

    # Second load: no migration, no notice
    txs2 = appio.load_ledger(str(ledger_path))
    err2 = capsys.readouterr().err
    assert "migrated" not in err2
    assert len(txs2) == 1


def test_migrate_dry_run_no_file_changes(tmp_path, capsys):
    """--dry-run prints a description and does NOT write .v1.bak or rewrite ledger."""
    ledger_path = tmp_path / "ledger.json"
    v1_data = [{"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
                "quantity": 1.0, "price_usd": 50000.0, "fee_usd": 0.0}]
    _write_json(ledger_path, v1_data)

    appio.migrate_command(str(ledger_path), dry_run=True)
    out = capsys.readouterr().out

    assert "would" in out.lower() or "dry" in out.lower() or "1 transaction" in out.lower()
    # Backup not created
    assert not os.path.exists(str(ledger_path) + ".v1.bak")
    # Ledger not rewritten (still V1)
    with open(ledger_path) as f:
        still_v1 = json.load(f)
    assert still_v1 == v1_data


def test_migrate_command_performs_upgrade(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.json"
    v1_data = [{"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
                "quantity": 1.0, "price_usd": 50000.0, "fee_usd": 0.0}]
    _write_json(ledger_path, v1_data)

    appio.migrate_command(str(ledger_path), dry_run=False)

    assert os.path.exists(str(ledger_path) + ".v1.bak")
    with open(ledger_path) as f:
        rewritten = json.load(f)
    assert "Buy" in rewritten[0]


def test_migrate_command_already_migrated(tmp_path, capsys):
    """If ledger is already in coinbasis schema, migrate prints a no-op message."""
    ledger_path = tmp_path / "ledger.json"
    _write_json(ledger_path, [])  # empty = coinbasis schema
    appio.migrate_command(str(ledger_path), dry_run=False)
    out = capsys.readouterr().out
    assert "already" in out.lower() or "no migration" in out.lower()
