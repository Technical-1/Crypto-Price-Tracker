"""CLI / dispatch + orchestration tests.

Package calls are mocked throughout — no real network or ledger math runs here.
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone

import appconfig
import coinbasis
import cryptolytics
import CryptoPriceTracker as cpt


# ── Task 17: appconfig.AppContext ─────────────────────────────────────────────

def test_appconfig_default_paths_are_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    monkeypatch.delenv("COINGECKO_PLAN", raising=False)
    monkeypatch.delenv("CPT_DATA_DIR", raising=False)

    ctx = appconfig.build_context_from_env(data_dir=None, method="fifo",
                                           select_file=None, offline=False)
    assert ctx.paths["ledger"].endswith("ledger.json")
    assert ctx.cg_config.api_key is None
    assert ctx.cg_config.plan == "demo"
    assert ctx.method == coinbasis.CostBasisMethod.FIFO


def test_appconfig_reads_api_key_from_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COINGECKO_API_KEY", "my-test-key")
    monkeypatch.setenv("COINGECKO_PLAN", "pro")

    ctx = appconfig.build_context_from_env(data_dir=None, method="fifo",
                                           select_file=None, offline=False)
    assert ctx.cg_config.api_key == "my-test-key"
    assert ctx.cg_config.plan == "pro"


def test_appconfig_data_dir_override(tmp_path, monkeypatch):
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ctx = appconfig.build_context_from_env(data_dir=str(tmp_path), method="fifo",
                                           select_file=None, offline=False)
    assert ctx.paths["ledger"].startswith(str(tmp_path))


def test_appconfig_method_hifo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ctx = appconfig.build_context_from_env(data_dir=None, method="hifo",
                                           select_file=None, offline=False)
    assert ctx.method == coinbasis.CostBasisMethod.HIFO


def test_appconfig_method_specific_requires_select(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        appconfig.build_context_from_env(data_dir=None, method="specific",
                                         select_file=None, offline=False)
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "--select" in err


# ── Task 18: parent parser + global flags ─────────────────────────────────────

def test_parser_global_method_flag():
    parser = cpt.build_parser()
    args = parser.parse_args(["tax", "--method", "hifo"])
    assert args.method == "hifo"


def test_parser_global_select_flag(tmp_path):
    sel_path = str(tmp_path / "sel.json")
    parser = cpt.build_parser()
    args = parser.parse_args(["tax", "--select", sel_path])
    assert args.select == sel_path


def test_parser_global_offline_flag():
    parser = cpt.build_parser()
    args = parser.parse_args(["prices", "--offline"])
    assert args.offline is True


def test_parser_global_data_dir_flag(tmp_path):
    parser = cpt.build_parser()
    args = parser.parse_args(["--data-dir", str(tmp_path), "tax"])
    assert args.data_dir == str(tmp_path)


def test_parser_no_subcommand_has_command_none():
    parser = cpt.build_parser()
    args = parser.parse_args([])
    assert getattr(args, "command", None) is None


def test_parser_unknown_flag_exits_2():
    with pytest.raises(SystemExit) as exc_info:
        cpt.cli(["--totally-unknown-flag-xyz"])
    assert exc_info.value.code == 2


def test_parser_method_choices():
    parser = cpt.build_parser()
    # all valid choices parse without error
    for m in ["fifo", "lifo", "hifo", "average", "specific"]:
        args = parser.parse_args(["tax", "--method", m])
        assert args.method == m


# ── Task 19: import / add / migrate dispatch ──────────────────────────────────

def test_import_csv_calls_appio(tmp_path, monkeypatch):
    """cli(['import', path]) delegates to appio.import_csv."""
    csv_path = tmp_path / "data.csv"
    ledger_path = tmp_path / "ledger.json"
    # Write empty coinbasis ledger
    with open(ledger_path, "w") as f:
        json.dump([], f)
    # Write minimal V1 CSV
    csv_path.write_text("date,coin,action,quantity,price_usd,fee_usd\n"
                        "2024-01-01,bitcoin,buy,1.0,50000,0\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    cpt.cli(["import", str(csv_path)])

    import appio
    txs = appio.load_ledger(str(ledger_path))
    assert len(txs) == 1


def test_import_missing_csv_exits_with_error(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        cpt.cli(["import", str(tmp_path / "nonexistent.csv")])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "not found" in err.lower() or "CSV" in err


def test_migrate_command_via_cli(tmp_path, capsys, monkeypatch):
    ledger_path = tmp_path / "ledger.json"
    with open(ledger_path, "w") as f:
        json.dump([
            {"date": "2024-01-01", "coin": "bitcoin", "action": "buy",
             "quantity": 1.0, "price_usd": 50000.0, "fee_usd": 0.0}
        ], f)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    cpt.cli(["migrate"])
    assert os.path.exists(str(ledger_path) + ".v1.bak")
