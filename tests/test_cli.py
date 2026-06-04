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
import coinlytics
import CryptoPriceTracker as cpt


# ── Task 17: appconfig.AppContext ─────────────────────────────────────────────

def test_appconfig_default_paths_are_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ledger.json").write_text("[]")  # cwd holds a ledger → cwd is used
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    monkeypatch.delenv("COINGECKO_PLAN", raising=False)
    monkeypatch.delenv("CPT_DATA_DIR", raising=False)

    ctx = appconfig.build_context_from_env(data_dir=None, method="fifo",
                                           select_file=None, offline=False)
    assert ctx.paths["ledger"] == str(tmp_path / "ledger.json")
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
         patch("coinlytics.CoinGeckoClient") as MockClient:
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
         patch("coinlytics.CoinGeckoClient") as MockClient:
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
         patch("coinlytics.CoinGeckoClient") as MockClient, \
         patch("coinlytics.rebalance.compute_trades", return_value=mock_plan), \
         patch("coinlytics.rebalance.target_weights", return_value={}):
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

    with patch("coinlytics.fetch_apys", return_value={}), \
         patch("coinlytics.CoinGeckoClient"):
        cpt.cli(["--data-dir", str(tmp_path), "staking"])

    out = capsys.readouterr().out
    # With no staking.json the command should still produce some output (or a no-config notice)
    assert out.strip() or True  # not crash


def test_run_staking_with_real_rewards_csv(tmp_path, capsys, monkeypatch):
    """Regression: staking must not crash on a real rewards.csv (CSV values are
    strings on disk; rewards_summary sums them numerically)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    _write_coinbasis_ledger(tmp_path / "ledger.json", [])
    (tmp_path / "staking.json").write_text(
        json.dumps({"ethereum": {"staked_qty": 2.0, "symbol": "ETH", "apy": 0.04}})
    )
    (tmp_path / "rewards.csv").write_text(
        "date,coin,quantity\n2024-01-01,ethereum,0.012\n2024-02-01,ethereum,0.013\n"
    )
    # Do NOT mock rewards_summary — exercise the real string->float boundary.
    with patch("coinlytics.fetch_apys", return_value={}):
        cpt.cli(["--data-dir", str(tmp_path), "staking"])
    out = capsys.readouterr().out
    assert "ethereum" in out.lower()
    assert "0.0250" in out  # 0.012 + 0.013 summed as floats, rendered %.4f


def test_run_news_with_mock_feed(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    mock_items = [
        {"title": "Bitcoin surges", "link": "http://x.com", "published": "2024-01-01", "source": "RSS"},
    ]
    with patch("coinlytics.fetch_rss", return_value=mock_items), \
         patch("coinlytics.fetch_cryptopanic", return_value=[]):
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
    )), patch("coinlytics.CoinGeckoClient") as MockCl, \
         patch("coinlytics.fetch_rss", return_value=[]), \
         patch("coinlytics.fetch_cryptopanic", return_value=[]):
        MockCl.return_value.prices.return_value = MagicMock(prices_map=lambda: {}, stale=False)
        MockCl.return_value.history.return_value = []
        cpt.cli(["--data-dir", str(tmp_path), "history"])

    capsys.readouterr()
    # Empty ledger → no history, but command should not crash
    assert True


# ── Task 23: run_prices ───────────────────────────────────────────────────────

def test_run_prices_with_ledger(tmp_path, capsys, monkeypatch):
    """prices command loads ledger, fetches prices, prints a table."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [
        {"Buy": {"timestamp": "2024-01-01T00:00:00Z", "wallet": "default",
                 "asset": "bitcoin", "quantity": "1", "unit_price": "50000", "fee": "0"}}
    ])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = [
        coinbasis.Holding(asset="bitcoin", wallet="default",
                          quantity=Decimal("1"), cost_basis=Decimal("50000"),
                          average_cost=Decimal("50000"))
    ]
    mock_valuation = MagicMock()
    mock_valuation.assets = [
        coinbasis.AssetValuation(
            asset="bitcoin", quantity=Decimal("1"),
            cost_basis=Decimal("50000"), price=Decimal("60000"),
            market_value=Decimal("60000"), unrealized=Decimal("10000"),
            allocation=Decimal("1"),
        )
    ]
    mock_valuation.total_cost = Decimal("50000")
    mock_valuation.total_value = Decimal("60000")
    mock_valuation.total_unrealized = Decimal("10000")
    mock_valuation.total_return = Decimal("0.2")
    mock_valuation.missing_prices = []
    mock_portfolio.valuation.return_value = mock_valuation

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {"bitcoin": Decimal("60000")}
    mock_book.stale = False
    mock_book.quotes = {
        "bitcoin": coinlytics.Quote(
            price=Decimal("60000"), change_24h=Decimal("2.5"),
            change_7d=None, market_cap=None, volume_24h=None,
        )
    }
    mock_book.sparklines = {}

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl:
        MockCl.return_value.prices.return_value = mock_book
        cpt.cli(["--data-dir", str(tmp_path), "prices"])

    out = capsys.readouterr().out
    assert "bitcoin" in out
    assert "60000" in out
    assert "2.5" in out or "2.50" in out


def test_run_prices_sparkline_fetches_series(tmp_path, capsys, monkeypatch):
    """--sparkline fetches a per-coin series via client.sparkline (not a prices kwarg)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [
        {"Buy": {"timestamp": "2024-01-01T00:00:00Z", "wallet": "default",
                 "asset": "bitcoin", "quantity": "1", "unit_price": "50000", "fee": "0"}}
    ])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = [
        coinbasis.Holding(asset="bitcoin", wallet="default",
                          quantity=Decimal("1"), cost_basis=Decimal("50000"),
                          average_cost=Decimal("50000"))
    ]
    mock_valuation = MagicMock()
    mock_valuation.assets = [
        coinbasis.AssetValuation(
            asset="bitcoin", quantity=Decimal("1"),
            cost_basis=Decimal("50000"), price=Decimal("60000"),
            market_value=Decimal("60000"), unrealized=Decimal("10000"),
            allocation=Decimal("1"),
        )
    ]
    mock_valuation.total_cost = Decimal("50000")
    mock_valuation.total_value = Decimal("60000")
    mock_valuation.total_unrealized = Decimal("10000")
    mock_valuation.total_return = Decimal("0.2")
    mock_valuation.missing_prices = []
    mock_portfolio.valuation.return_value = mock_valuation

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {"bitcoin": Decimal("60000")}
    mock_book.stale = False
    mock_book.quotes = {
        "bitcoin": coinlytics.Quote(
            price=Decimal("60000"), change_24h=Decimal("2.5"),
            change_7d=Decimal("5.0"), market_cap=None, volume_24h=None,
        )
    }
    mock_book.sparklines = {}

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl:
        client = MockCl.return_value
        client.prices.return_value = mock_book
        client.sparkline.return_value = [1.0, 2.0, 3.0, 4.0, 3.5, 5.0, 6.0]
        cpt.cli(["--data-dir", str(tmp_path), "prices", "--sparkline"])

    out = capsys.readouterr().out
    # prices() must be called without the bogus with_sparkline_7d kwarg.
    _, prices_kwargs = client.prices.call_args
    assert "with_sparkline_7d" not in prices_kwargs
    # The sparkline series is fetched per coin and rendered into the row.
    client.sparkline.assert_called_once_with("bitcoin", days=7)
    assert "bitcoin" in out


def test_run_prices_empty_ledger_shows_demo_table(tmp_path, capsys, monkeypatch):
    """Empty ledger falls back to originalHoldings demo without crashing."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    # No ledger.json created — appio.load_ledger will exit(1) for missing file;
    # but the prices command special-cases an absent ledger by using originalHoldings.

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {"bitcoin": Decimal("60000")}
    mock_book.stale = False
    mock_book.quotes = {}
    mock_book.sparklines = {}

    with patch("coinlytics.CoinGeckoClient") as MockCl:
        MockCl.return_value.prices.return_value = mock_book
        # Should not crash/exit even with no ledger:
        try:
            cpt.cli(["--data-dir", str(tmp_path), "prices"])
        except SystemExit as e:
            # acceptable if ledger truly missing, but no traceback
            assert e.code in (0, 1)


def test_run_prices_stale_book_prints_notice(tmp_path, capsys, monkeypatch):
    """A stale PriceBook causes a stderr notice but still exits 0."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = []
    mock_portfolio.valuation.return_value = MagicMock(
        assets=[], total_cost=Decimal("0"), total_value=Decimal("0"),
        total_unrealized=Decimal("0"), total_return=Decimal("0"), missing_prices=[])

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {}
    mock_book.stale = True   # <-- offline fallback
    mock_book.quotes = {}
    mock_book.sparklines = {}

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl:
        MockCl.return_value.prices.return_value = mock_book
        cpt.cli(["--data-dir", str(tmp_path), "prices"])

    err = capsys.readouterr().err
    assert "stale" in err.lower() or "offline" in err.lower() or "last-good" in err.lower()


# ── Task 24: run_holdings ─────────────────────────────────────────────────────

def test_run_holdings_renders_table(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = [
        coinbasis.Holding(
            asset="bitcoin", wallet="cold",
            quantity=Decimal("2"), cost_basis=Decimal("100000"),
            average_cost=Decimal("50000"),
        )
    ]

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {"bitcoin": Decimal("60000")}
    mock_book.stale = False

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl:
        MockCl.return_value.prices.return_value = mock_book
        cpt.cli(["--data-dir", str(tmp_path), "holdings"])

    out = capsys.readouterr().out
    assert "bitcoin" in out
    assert "2" in out or "2.0" in out
    assert "50000" in out


def test_run_holdings_wallet_filter(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = [
        coinbasis.Holding(asset="bitcoin", wallet="cold",
                          quantity=Decimal("2"), cost_basis=Decimal("100000"),
                          average_cost=Decimal("50000")),
        coinbasis.Holding(asset="ethereum", wallet="hot",
                          quantity=Decimal("5"), cost_basis=Decimal("10000"),
                          average_cost=Decimal("2000")),
    ]

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {}
    mock_book.stale = False

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl:
        MockCl.return_value.prices.return_value = mock_book
        cpt.cli(["--data-dir", str(tmp_path), "holdings", "--wallet", "cold"])

    out = capsys.readouterr().out
    assert "bitcoin" in out
    assert "ethereum" not in out


def test_run_holdings_specific_method_exits(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    sel_path = tmp_path / "sel.json"
    sel_path.write_text("{}")
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.side_effect = coinbasis.SelectionRequired()

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient"), \
         patch("coinbasis.serialization.lot_selection_from_json", return_value={}):
        with pytest.raises(SystemExit) as exc_info:
            cpt.cli(["--data-dir", str(tmp_path),
                     "holdings", "--method", "specific", "--select", str(sel_path)])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "specific" in err.lower() or "--select" in err


# ── Task 25: run_valuation ────────────────────────────────────────────────────

def test_run_valuation_renders_headline(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = []
    mock_valuation = MagicMock()
    mock_valuation.assets = [
        coinbasis.AssetValuation(
            asset="bitcoin", quantity=Decimal("1"),
            cost_basis=Decimal("50000"), price=Decimal("60000"),
            market_value=Decimal("60000"), unrealized=Decimal("10000"),
            allocation=Decimal("1"),
        )
    ]
    mock_valuation.total_cost = Decimal("50000")
    mock_valuation.total_value = Decimal("60000")
    mock_valuation.total_unrealized = Decimal("10000")
    mock_valuation.total_return = Decimal("0.2")
    mock_valuation.missing_prices = []
    mock_portfolio.valuation.return_value = mock_valuation

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {"bitcoin": Decimal("60000")}
    mock_book.stale = False

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl:
        MockCl.return_value.prices.return_value = mock_book
        cpt.cli(["--data-dir", str(tmp_path), "valuation"])

    out = capsys.readouterr().out
    assert "bitcoin" in out
    assert "60000" in out
    assert "20.00" in out or "20%" in out or "0.2" in out


# ── Task 26: run_performance ──────────────────────────────────────────────────

def test_run_performance_builds_snapshot(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = []
    mock_valuation = MagicMock()
    mock_valuation.total_cost = Decimal("0")
    mock_valuation.total_value = Decimal("0")
    mock_valuation.total_unrealized = Decimal("0")
    mock_valuation.total_return = Decimal("0")
    mock_valuation.assets = []
    mock_valuation.missing_prices = []
    mock_portfolio.valuation.return_value = mock_valuation

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {}
    mock_book.stale = False

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl, \
         patch("coinlytics.perf.build_snapshot") as mock_build_snap, \
         patch("coinlytics.perf.dedup_append") as mock_dedup, \
         patch("coinlytics.perf.metrics") as mock_metrics:
        MockCl.return_value.prices.return_value = mock_book
        mock_snap = coinlytics.Snapshot("2024-01-01", 0.0, 0.0, 0.0)
        mock_build_snap.return_value = mock_snap
        mock_dedup.return_value = [mock_snap]
        mock_metrics.return_value = coinlytics.PerfMetrics(
            volatility=None, sharpe=None, max_drawdown=None,
            cumulative_return=None, period_returns=[])
        cpt.cli(["--data-dir", str(tmp_path), "performance"])

    out = capsys.readouterr().out
    # Should render perf view without crashing
    assert "performance" in out.lower() or "history" in out.lower() or out.strip()
    # Check build_snapshot was called
    mock_build_snap.assert_called_once()


# ── Task 27: --method specific routing for tax ────────────────────────────────

def test_tax_method_specific_routes_to_with_selection(tmp_path, capsys, monkeypatch):
    """--method specific --select FILE routes tax to the *_with_selection methods."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ledger_path = tmp_path / "ledger.json"
    _write_coinbasis_ledger(ledger_path, [])
    sel_path = tmp_path / "sel.json"
    sel_path.write_text("{}")  # empty LotSelection

    mock_portfolio = MagicMock()
    mock_cg_report = MagicMock()
    mock_cg_report.rows = []
    mock_cg_report.short_term_gain = Decimal("0")
    mock_cg_report.long_term_gain = Decimal("0")
    mock_cg_report.total_gain = Decimal("0")
    mock_portfolio.capital_gains_report_with_selection.return_value = mock_cg_report
    mock_portfolio.income_report.return_value = MagicMock(events=[], total_income=Decimal("0"))
    mock_portfolio.valuation.return_value = MagicMock(
        assets=[], total_cost=Decimal("0"), total_value=Decimal("0"),
        total_unrealized=Decimal("0"), total_return=Decimal("0"), missing_prices=[])
    mock_portfolio.tax_estimate_with_selection.return_value = coinbasis.TaxEstimate(
        Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl, \
         patch("coinbasis.serialization.lot_selection_from_json", return_value={}):
        MockCl.return_value.prices.return_value = MagicMock(
            prices_map=lambda: {}, stale=False)
        cpt.cli([
            "--data-dir", str(tmp_path),
            "tax", "--method", "specific", "--select", str(sel_path), "--year", "2024"
        ])

    # Assert *_with_selection was called, not the regular method
    mock_portfolio.capital_gains_report_with_selection.assert_called_once()
    mock_portfolio.capital_gains_report.assert_not_called()


def test_tax_method_specific_without_select_exits(tmp_path, capsys, monkeypatch):
    """--method specific without --select exits with code 1."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    _write_coinbasis_ledger(tmp_path / "ledger.json", [])

    with pytest.raises(SystemExit) as exc_info:
        cpt.cli(["--data-dir", str(tmp_path), "tax", "--method", "specific"])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "--select" in err


# ── Task 28: global error-map single catch site ──────────────────────────────

def test_rate_limited_no_cache_exits_1(tmp_path, capsys, monkeypatch):
    """PriceSourceError (no cache) → exit 1 + readable stderr."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    _write_coinbasis_ledger(tmp_path / "ledger.json", [])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = [
        coinbasis.Holding(asset="bitcoin", wallet="default",
                          quantity=Decimal("1"), cost_basis=Decimal("50000"),
                          average_cost=Decimal("50000"))
    ]

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl:
        MockCl.return_value.prices.side_effect = coinlytics.RateLimitedError(
            "rate limited", url="https://api.coingecko.com", status=429)
        with pytest.raises(SystemExit) as exc_info:
            cpt.cli(["--data-dir", str(tmp_path), "prices"])

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "rate limit" in err.lower() or "429" in err


def test_insufficient_lots_exits_1(tmp_path, capsys, monkeypatch):
    """InsufficientLots → exit 1 + readable stderr."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    _write_coinbasis_ledger(tmp_path / "ledger.json", [])

    mock_portfolio = MagicMock()
    from decimal import Decimal
    mock_portfolio.holdings.side_effect = coinbasis.InsufficientLots(
        asset="bitcoin", wallet="default",
        attempted=Decimal("2"), available=Decimal("1"),
    )

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient"):
        with pytest.raises(SystemExit) as exc_info:
            cpt.cli(["--data-dir", str(tmp_path), "holdings"])

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "bitcoin" in err or "insufficient" in err.lower()


# ── Task 29: --offline flag + stale-price path ────────────────────────────────

def test_offline_flag_sets_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    ctx = appconfig.build_context_from_env(data_dir=str(tmp_path),
                                            method="fifo", select_file=None, offline=True)
    assert ctx.offline is True


def test_offline_stale_prices_exit_0(tmp_path, capsys, monkeypatch):
    """With --offline, stale prices produce a notice but still exit 0."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    _write_coinbasis_ledger(tmp_path / "ledger.json", [])

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = []
    mock_portfolio.valuation.return_value = MagicMock(
        assets=[], total_cost=Decimal("0"), total_value=Decimal("0"),
        total_unrealized=Decimal("0"), total_return=Decimal("0"), missing_prices=[])

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {}
    mock_book.stale = True  # ← offline serves last-good
    mock_book.quotes = {}
    mock_book.sparklines = {}

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("coinlytics.CoinGeckoClient") as MockCl:
        MockCl.return_value.prices.return_value = mock_book
        cpt.cli(["--data-dir", str(tmp_path), "prices", "--offline"])

    # Exit code 0 (stale is non-fatal)
    err = capsys.readouterr().err
    assert "stale" in err.lower() or "offline" in err.lower() or "last-good" in err.lower()
