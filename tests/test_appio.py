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
