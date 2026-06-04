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


def test_load_taxconfig_returns_default_when_missing(tmp_path):
    tc = appio.load_taxconfig(str(tmp_path / "taxconfig.json"))
    assert isinstance(tc, coinbasis.TaxConfig)
    assert tc.jurisdiction == "US"


def test_load_taxconfig_parses_file(tmp_path):
    cfg_path = tmp_path / "taxconfig.json"
    _write_json(cfg_path, {
        "jurisdiction": "CA",
        "long_term_threshold_days": 365,
        "short_term_rate": "0.33",
        "long_term_brackets": [{"up_to": None, "rate": "0.15"}],
    })
    tc = appio.load_taxconfig(str(cfg_path))
    assert tc.jurisdiction == "CA"
    assert tc.short_term_rate == Decimal("0.33")


def test_load_targets_returns_decimal_weights(tmp_path):
    p = tmp_path / "targets.json"
    _write_json(p, {"bitcoin": 0.6, "ethereum": 0.4})
    targets = appio.load_targets(str(p))
    assert targets["bitcoin"] == Decimal("0.6")
    assert targets["ethereum"] == Decimal("0.4")


def test_load_targets_missing_returns_none(tmp_path):
    result = appio.load_targets(str(tmp_path / "targets.json"))
    assert result is None


def test_load_news_config_defaults_on_missing(tmp_path):
    cfg = appio.load_news_config(str(tmp_path / "news.json"))
    assert "feeds" in cfg
    assert cfg["feeds"] == list(cryptolytics.DEFAULT_FEEDS)


def test_load_rewards_csv(tmp_path):
    p = tmp_path / "rewards.csv"
    with open(p, "w", newline="") as f:
        writer = _csv.writer(f)
        writer.writerow(["date", "coin", "quantity"])
        writer.writerow(["2024-01-01", "ethereum", "0.5"])
    rewards = appio.load_rewards(str(p))
    assert len(rewards) == 1
    assert rewards[0]["coin"] == "ethereum"
    assert rewards[0]["quantity"] == "0.5"


def test_snapshots_round_trip(tmp_path):
    path = str(tmp_path / "snapshots.jsonl")
    snap1 = cryptolytics.Snapshot(date="2024-01-01", total_value=1000.0, cost=800.0, pl=200.0)
    snap2 = cryptolytics.Snapshot(date="2024-01-02", total_value=1100.0, cost=800.0, pl=300.0)

    appio.save_snapshots(path, [snap1, snap2])
    loaded = appio.load_snapshots(path)

    assert len(loaded) == 2
    assert loaded[0] == snap1
    assert loaded[1] == snap2


def test_load_snapshots_missing_returns_empty(tmp_path):
    result = appio.load_snapshots(str(tmp_path / "snapshots.jsonl"))
    assert result == []


def test_save_snapshots_is_atomic(tmp_path):
    """save_snapshots should not leave a corrupt file on success."""
    path = str(tmp_path / "snapshots.jsonl")
    snaps = [cryptolytics.Snapshot(date="2024-01-01", total_value=500.0, cost=400.0, pl=100.0)]
    appio.save_snapshots(path, snaps)
    assert os.path.exists(path)
    loaded = appio.load_snapshots(path)
    assert loaded == snaps


def _write_csv(path, rows, headers=None):
    """Write a list-of-dicts CSV."""
    if not rows:
        return
    hdrs = headers or list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = _csv.DictWriter(f, fieldnames=hdrs)
        writer.writeheader()
        writer.writerows(rows)


def test_import_csv_v1_columns(tmp_path):
    csv_path = tmp_path / "import.csv"
    ledger_path = tmp_path / "ledger.json"
    _write_json(ledger_path, [])  # empty coinbasis ledger

    rows = [
        {"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
         "quantity": "1.0", "price_usd": "50000", "fee_usd": "0"},
    ]
    _write_csv(csv_path, rows)

    appio.import_csv(str(csv_path), str(ledger_path))

    txs = appio.load_ledger(str(ledger_path))
    assert len(txs) == 1
    assert isinstance(txs[0], coinbasis.Buy)
    assert txs[0].asset == "bitcoin"


def test_import_csv_deduplicates(tmp_path):
    csv_path = tmp_path / "import.csv"
    ledger_path = tmp_path / "ledger.json"
    _write_json(ledger_path, [])

    rows = [{"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
             "quantity": "1.0", "price_usd": "50000", "fee_usd": "0"}]
    _write_csv(csv_path, rows)

    appio.import_csv(str(csv_path), str(ledger_path))
    # Import again — same data → dedup, still 1 tx
    appio.import_csv(str(csv_path), str(ledger_path))

    txs = appio.load_ledger(str(ledger_path))
    assert len(txs) == 1


def test_import_csv_skips_invalid_rows(tmp_path, capsys):
    csv_path = tmp_path / "import.csv"
    ledger_path = tmp_path / "ledger.json"
    _write_json(ledger_path, [])

    rows = [
        {"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
         "quantity": "-5.0", "price_usd": "50000", "fee_usd": "0"},  # invalid qty
        {"date": "2024-01-02", "coin": "bitcoin", "action": "buy",
         "quantity": "1.0", "price_usd": "50000", "fee_usd": "0"},   # valid
    ]
    _write_csv(csv_path, rows)
    appio.import_csv(str(csv_path), str(ledger_path))

    txs = appio.load_ledger(str(ledger_path))
    assert len(txs) == 1  # only the valid row
    err = capsys.readouterr().err
    assert "skipped CSV line" in err


def test_import_csv_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        appio.import_csv(str(tmp_path / "missing.csv"), str(tmp_path / "ledger.json"))
    assert exc_info.value.code == 1
