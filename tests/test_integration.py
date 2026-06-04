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
