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
