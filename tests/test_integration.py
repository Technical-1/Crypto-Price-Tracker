"""Integration tests: full appio → package call → formatter pipeline, mocked."""
from __future__ import annotations

import json
import os
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
import coinbasis
import cryptolytics
import appio
import CryptoPriceTracker as cpt


# ── Migration integration ─────────────────────────────────────────────────────

def test_migration_end_to_end(tmp_v1_ledger, tmp_path, capsys):
    """load_ledger on a V1 file: migrates in-place, writes .v1.bak, prints notice."""
    ledger_path = tmp_v1_ledger
    txs = appio.load_ledger(ledger_path)

    err = capsys.readouterr().err
    assert "migrated" in err
    assert ".v1.bak" in err

    # Backup created
    assert os.path.exists(ledger_path + ".v1.bak")

    # 2 transactions (buy + sell)
    assert len(txs) == 2
    assert isinstance(txs[0], coinbasis.Buy)
    assert isinstance(txs[1], coinbasis.Sell)

    # Both in DEFAULT_WALLET
    assert all(tx.wallet == "default" for tx in txs)

    # Timestamps are UTC midnight
    from datetime import datetime, timezone
    assert txs[0].timestamp == datetime(2022, 1, 1, tzinfo=timezone.utc)

    # Quantities are Decimal
    assert txs[0].quantity == Decimal("1.0")


def test_migration_idempotent(tmp_v1_ledger, tmp_path, capsys):
    """Second load of the migrated file does NOT re-migrate."""
    appio.load_ledger(tmp_v1_ledger)
    capsys.readouterr()  # consume first-load stderr

    appio.load_ledger(tmp_v1_ledger)
    err2 = capsys.readouterr().err
    assert "migrated" not in err2


def test_migration_backup_not_overwritten(tmp_v1_ledger, tmp_path, capsys):
    """If .v1.bak already exists, it is NOT overwritten."""
    bak_path = tmp_v1_ledger + ".v1.bak"
    with open(bak_path, "w") as f:
        f.write("pre-existing-backup")

    appio.load_ledger(tmp_v1_ledger)

    with open(bak_path) as f:
        content = f.read()
    assert content == "pre-existing-backup"


def test_migrate_cli_command_end_to_end(tmp_path, capsys, monkeypatch, v1_ledger_data):
    ledger_path = tmp_path / "ledger.json"
    with open(ledger_path, "w") as f:
        json.dump(v1_ledger_data, f)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    cpt.cli(["migrate"])

    assert os.path.exists(str(ledger_path) + ".v1.bak")
    with open(ledger_path) as f:
        rewritten = json.load(f)
    assert "Buy" in rewritten[0]


def test_migrate_dry_run_via_cli(tmp_path, capsys, monkeypatch, v1_ledger_data):
    ledger_path = tmp_path / "ledger.json"
    with open(ledger_path, "w") as f:
        json.dump(v1_ledger_data, f)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    cpt.cli(["migrate", "--dry-run"])

    # Backup NOT created
    assert not os.path.exists(str(ledger_path) + ".v1.bak")
    out = capsys.readouterr().out
    assert "dry" in out.lower() or "would" in out.lower()


# ── Config loader + snapshot round-trip integration ────────────────────────────

def test_taxconfig_default_on_missing(tmp_path):
    tc = appio.load_taxconfig(str(tmp_path / "taxconfig.json"))
    assert isinstance(tc, coinbasis.TaxConfig)
    assert tc.jurisdiction == "US"


def test_taxconfig_parses_and_uses_in_estimate(tmp_path):
    cfg_path = tmp_path / "taxconfig.json"
    with open(cfg_path, "w") as f:
        json.dump({
            "jurisdiction": "US",
            "long_term_threshold_days": 365,
            "short_term_rate": "0.35",
            "long_term_brackets": [
                {"up_to": "47025", "rate": "0"},
                {"up_to": "518900", "rate": "0.15"},
                {"up_to": None, "rate": "0.20"},
            ],
        }, f)
    tc = appio.load_taxconfig(str(cfg_path))
    est = coinbasis.tax.estimate(
        short_gain=Decimal("1000"),
        long_gain=Decimal("20000"),
        config=tc,
    )
    # short tax = 1000 * 0.35 = 350; long gain 20000 < 47025 → 0
    assert est.short_term_tax == Decimal("350")
    assert est.long_term_tax == Decimal("0")


def test_targets_loads_as_decimal_weights(tmp_path):
    path = tmp_path / "targets.json"
    with open(path, "w") as f:
        json.dump({"bitcoin": 0.6, "ethereum": 0.4}, f)
    targets = appio.load_targets(str(path))
    assert targets["bitcoin"] + targets["ethereum"] == Decimal("1.0")


def test_snapshot_append_dedup_round_trip(tmp_path):
    """Append the same snapshot twice → only one stored; new date → two stored."""
    snap_path = str(tmp_path / "snapshots.jsonl")
    snap1 = cryptolytics.Snapshot(date="2024-01-01", total_value=1000.0, cost=800.0, pl=200.0)
    snap2 = cryptolytics.Snapshot(date="2024-01-02", total_value=1100.0, cost=800.0, pl=300.0)
    snap1_updated = cryptolytics.Snapshot(date="2024-01-01", total_value=1050.0, cost=800.0, pl=250.0)

    # First write
    loaded = appio.load_snapshots(snap_path)  # []
    updated = cryptolytics.dedup_append(loaded, snap1)
    appio.save_snapshots(snap_path, updated)

    # Second write same date (should replace)
    loaded2 = appio.load_snapshots(snap_path)
    updated2 = cryptolytics.dedup_append(loaded2, snap1_updated)
    appio.save_snapshots(snap_path, updated2)

    # Third write new date
    loaded3 = appio.load_snapshots(snap_path)
    updated3 = cryptolytics.dedup_append(loaded3, snap2)
    appio.save_snapshots(snap_path, updated3)

    final = appio.load_snapshots(snap_path)
    assert len(final) == 2  # 2024-01-01 (updated) + 2024-01-02
    dates = {s.date for s in final}
    assert "2024-01-01" in dates
    assert "2024-01-02" in dates
    # 2024-01-01 was replaced with the updated value
    jan1 = next(s for s in final if s.date == "2024-01-01")
    assert jan1.total_value == 1050.0
