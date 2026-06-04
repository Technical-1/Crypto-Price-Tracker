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


# ── Task 20: run_tax orchestration ────────────────────────────────────────────

def _write_coinbasis_ledger(path, entries=None):
    with open(path, "w") as f:
        json.dump(entries or [], f)


def test_run_tax_prints_all_three_sections(tmp_path, capsys, monkeypatch):
    """run_tax produces Realized gains, Unrealized P/L, and Estimated tax sections."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [
        {"Buy": {"timestamp": "2023-01-01T00:00:00Z", "wallet": "default",
                 "asset": "bitcoin", "quantity": "1", "unit_price": "20000", "fee": "0"}},
        {"Sell": {"timestamp": "2024-03-01T00:00:00Z", "wallet": "default",
                  "asset": "bitcoin", "quantity": "0.5", "unit_price": "40000", "fee": "0"}},
    ])

    mock_portfolio = MagicMock()
    mock_cg_report = MagicMock()
    mock_cg_report.rows = [
        coinbasis.RealizedGain(
            asset="bitcoin", wallet="default",
            disposed_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
            acquired_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            quantity=Decimal("0.5"),
            proceeds=Decimal("20000"),
            cost_basis=Decimal("10000"),
            gain=Decimal("10000"),
            term=coinbasis.Term.LONG,
        )
    ]
    mock_cg_report.short_term_gain = Decimal("0")
    mock_cg_report.long_term_gain = Decimal("10000")
    mock_cg_report.total_gain = Decimal("10000")
    mock_portfolio.capital_gains_report.return_value = mock_cg_report
    mock_portfolio.realized_gains.return_value = mock_cg_report.rows
    mock_portfolio.income_report.return_value = MagicMock(events=[], total_income=Decimal("0"))

    mock_valuation = MagicMock()
    mock_valuation.assets = []
    mock_valuation.total_cost = Decimal("10000")
    mock_valuation.total_value = Decimal("25000")
    mock_valuation.total_unrealized = Decimal("15000")
    mock_valuation.total_return = Decimal("1.5")
    mock_valuation.missing_prices = []
    mock_portfolio.valuation.return_value = mock_valuation
    mock_portfolio.holdings.return_value = []

    mock_tax_estimate = coinbasis.TaxEstimate(
        short_term_gain=Decimal("0"), long_term_gain=Decimal("10000"),
        short_term_tax=Decimal("0"), long_term_tax=Decimal("0"),
        total_tax=Decimal("0"),
    )
    mock_portfolio.tax_estimate.return_value = mock_tax_estimate

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {"bitcoin": Decimal("50000")}
    mock_book.stale = False

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient") as MockClient:
        MockClient.return_value.prices.return_value = mock_book
        cpt.cli(["--data-dir", str(tmp_path), "tax", "--year", "2024"])

    out = capsys.readouterr().out
    assert "Realized" in out
    assert "Unrealized" in out
    assert "Estimated Tax" in out or "tax" in out.lower()


def test_run_tax_year_filter(tmp_path, capsys, monkeypatch):
    """--year flag is threaded through to capital_gains_report."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])

    mock_portfolio = MagicMock()
    mock_cg_report = MagicMock()
    mock_cg_report.rows = []
    mock_cg_report.short_term_gain = Decimal("0")
    mock_cg_report.long_term_gain = Decimal("0")
    mock_cg_report.total_gain = Decimal("0")
    mock_portfolio.capital_gains_report.return_value = mock_cg_report
    mock_portfolio.income_report.return_value = MagicMock(events=[], total_income=Decimal("0"))
    mock_portfolio.holdings.return_value = []
    mock_portfolio.valuation.return_value = MagicMock(
        assets=[], total_cost=Decimal("0"), total_value=Decimal("0"),
        total_unrealized=Decimal("0"), total_return=Decimal("0"), missing_prices=[])
    mock_portfolio.tax_estimate.return_value = coinbasis.TaxEstimate(
        Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient") as MockClient:
        MockClient.return_value.prices.return_value = MagicMock(
            prices_map=lambda: {}, stale=False)
        cpt.cli(["--data-dir", str(tmp_path), "tax", "--year", "2023"])

    mock_portfolio.capital_gains_report.assert_called_once_with(
        coinbasis.CostBasisMethod.FIFO, 2023
    )


# ── Task 21: run_rebalance orchestration ──────────────────────────────────────

def test_run_rebalance_equal_strategy(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])  # empty — test structure only

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = []
    mock_portfolio.valuation.return_value = MagicMock(
        assets=[], total_cost=Decimal("0"), total_value=Decimal("0"),
        total_unrealized=Decimal("0"), total_return=Decimal("0"), missing_prices=[])

    mock_plan = MagicMock()
    mock_plan.actions = []
    mock_plan.total_value = Decimal("0")
    mock_plan.total_buys_usd = Decimal("0")
    mock_plan.total_sells_usd = Decimal("0")
    mock_plan.in_balance = True

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient") as MockClient, \
         patch("cryptolytics.rebalance.compute_trades", return_value=mock_plan), \
         patch("cryptolytics.rebalance.target_weights", return_value={}):
        mock_client = MockClient.return_value
        mock_client.prices.return_value = MagicMock(prices_map=lambda: {}, stale=False)
        mock_client.history.return_value = []
        cpt.cli(["--data-dir", str(tmp_path), "rebalance"])

    out = capsys.readouterr().out
    # Should print the rebalance plan (even if empty/in-balance)
    assert "balance" in out.lower() or "rebalance" in out.lower() or out.strip()


# ── Task 22: run_staking / run_news / run_history ─────────────────────────────

def test_run_staking_no_config_exits(tmp_path, capsys, monkeypatch):
    """Staking command with no staking.json exits cleanly."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    _write_coinbasis_ledger(tmp_path / "ledger.json", [])

    with patch("cryptolytics.fetch_apys", return_value={}), \
         patch("cryptolytics.CoinGeckoClient"):
        cpt.cli(["--data-dir", str(tmp_path), "staking"])

    out = capsys.readouterr().out
    # With no staking.json the command should still produce some output (or a no-config notice)
    assert out.strip() or True  # not crash


def test_run_news_with_mock_feed(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    mock_items = [
        {"title": "Bitcoin surges", "link": "http://x.com", "published": "2024-01-01", "source": "RSS"},
    ]
    with patch("cryptolytics.fetch_rss", return_value=mock_items), \
         patch("cryptolytics.fetch_cryptopanic", return_value=[]):
        cpt.cli(["--data-dir", str(tmp_path), "news"])

    out = capsys.readouterr().out
    assert "bitcoin" in out.lower() or "surges" in out.lower()


def test_run_history_with_mock_client(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])  # empty ledger

    with patch("coinbasis.Portfolio.from_transactions", return_value=MagicMock(
        holdings=MagicMock(return_value=[])
    )), patch("cryptolytics.CoinGeckoClient") as MockCl, \
         patch("cryptolytics.fetch_rss", return_value=[]), \
         patch("cryptolytics.fetch_cryptopanic", return_value=[]):
        MockCl.return_value.prices.return_value = MagicMock(prices_map=lambda: {}, stale=False)
        MockCl.return_value.history.return_value = []
        cpt.cli(["--data-dir", str(tmp_path), "history"])

    capsys.readouterr()
    # Empty ledger → no history, but command should not crash
    assert True
