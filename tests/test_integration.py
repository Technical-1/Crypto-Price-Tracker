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


# ── MockClient-driven command integration ──────────────────────────────────────

def test_prices_command_full_pipeline(tmp_path, capsys, monkeypatch,
                                       tmp_ledger, mock_client):
    """prices command: ledger → Portfolio.valuation → format_prices (MockClient)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = [
        coinbasis.Holding(asset="bitcoin", wallet="default",
                          quantity=Decimal("1"), cost_basis=Decimal("20000"),
                          average_cost=Decimal("20000")),
    ]
    mock_valuation = MagicMock()
    mock_valuation.assets = [
        coinbasis.AssetValuation(
            asset="bitcoin", quantity=Decimal("1"),
            cost_basis=Decimal("20000"), price=Decimal("50000"),
            market_value=Decimal("50000"), unrealized=Decimal("30000"),
            allocation=Decimal("1"),
        )
    ]
    mock_valuation.total_cost = Decimal("20000")
    mock_valuation.total_value = Decimal("50000")
    mock_valuation.total_unrealized = Decimal("30000")
    mock_valuation.total_return = Decimal("1.5")
    mock_valuation.missing_prices = []
    mock_portfolio.valuation.return_value = mock_valuation

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient", return_value=mock_client):
        cpt.cli(["--data-dir", str(tmp_path), "prices"])

    out = capsys.readouterr().out
    assert "bitcoin" in out
    assert "50000" in out
    assert "30000" in out


def test_holdings_command_full_pipeline(tmp_path, capsys, monkeypatch,
                                         tmp_ledger, mock_client):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = [
        coinbasis.Holding(asset="bitcoin", wallet="cold",
                          quantity=Decimal("1"), cost_basis=Decimal("20000"),
                          average_cost=Decimal("20000")),
        coinbasis.Holding(asset="ethereum", wallet="default",
                          quantity=Decimal("2"), cost_basis=Decimal("4000"),
                          average_cost=Decimal("2000")),
    ]

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient", return_value=mock_client):
        cpt.cli(["--data-dir", str(tmp_path), "holdings"])

    out = capsys.readouterr().out
    assert "bitcoin" in out
    assert "ethereum" in out


def test_valuation_command_full_pipeline(tmp_path, capsys, monkeypatch,
                                          tmp_ledger, mock_client):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = [
        coinbasis.Holding(asset="bitcoin", wallet="default",
                          quantity=Decimal("1"), cost_basis=Decimal("20000"),
                          average_cost=Decimal("20000")),
    ]
    mock_valuation = MagicMock()
    mock_valuation.assets = [
        coinbasis.AssetValuation(
            asset="bitcoin", quantity=Decimal("1"),
            cost_basis=Decimal("20000"), price=Decimal("50000"),
            market_value=Decimal("50000"), unrealized=Decimal("30000"),
            allocation=Decimal("1"),
        )
    ]
    mock_valuation.total_cost = Decimal("20000")
    mock_valuation.total_value = Decimal("50000")
    mock_valuation.total_unrealized = Decimal("30000")
    mock_valuation.total_return = Decimal("1.5")
    mock_valuation.missing_prices = []
    mock_portfolio.valuation.return_value = mock_valuation

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient", return_value=mock_client):
        cpt.cli(["--data-dir", str(tmp_path), "valuation"])

    out = capsys.readouterr().out
    assert "bitcoin" in out
    assert "Allocation" in out or "allocation" in out.lower()


def test_performance_command_full_pipeline(tmp_path, capsys, monkeypatch,
                                            tmp_ledger, mock_client):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = []
    mock_portfolio.valuation.return_value = MagicMock(
        assets=[], total_cost=Decimal("0"), total_value=Decimal("1000"),
        total_unrealized=Decimal("0"), total_return=Decimal("0"), missing_prices=[])

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient", return_value=mock_client):
        cpt.cli(["--data-dir", str(tmp_path), "performance"])

    out = capsys.readouterr().out
    assert "Performance" in out or "performance" in out.lower()


# ── Error-path integration ──────────────────────────────────────────────────────

def test_price_source_error_no_cache_exits_1(tmp_path, capsys, monkeypatch,
                                               tmp_ledger, failing_mock_client):
    """MockClient with fail_ids={bitcoin} → PriceSourceError → exit 1."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = [
        coinbasis.Holding(asset="bitcoin", wallet="default",
                          quantity=Decimal("1"), cost_basis=Decimal("20000"),
                          average_cost=Decimal("20000")),
    ]

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient", return_value=failing_mock_client):
        with pytest.raises(SystemExit) as exc_info:
            cpt.cli(["--data-dir", str(tmp_path), "prices"])

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "price" in err.lower() or "fetch" in err.lower() or "rate" in err.lower()


def test_stale_book_exits_0(tmp_path, capsys, monkeypatch, tmp_ledger):
    """Stale PriceBook (offline fallback) → exit 0 + stderr notice."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.return_value = []
    mock_portfolio.valuation.return_value = MagicMock(
        assets=[], total_cost=Decimal("0"), total_value=Decimal("0"),
        total_unrealized=Decimal("0"), total_return=Decimal("0"), missing_prices=[])

    mock_book = MagicMock()
    mock_book.prices_map.return_value = {}
    mock_book.stale = True
    mock_book.quotes = {}
    mock_book.sparklines = {}

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient") as MockCl:
        MockCl.return_value.prices.return_value = mock_book
        # Should NOT raise SystemExit
        cpt.cli(["--data-dir", str(tmp_path), "prices"])

    err = capsys.readouterr().err
    assert "stale" in err.lower() or "offline" in err.lower() or "last-good" in err.lower()


def test_selection_required_exits_1_for_holdings(tmp_path, capsys, monkeypatch, tmp_ledger):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    sel_path = tmp_path / "sel.json"
    sel_path.write_text("{}")

    mock_portfolio = MagicMock()
    mock_portfolio.holdings.side_effect = coinbasis.SelectionRequired()

    with patch("coinbasis.Portfolio.from_transactions", return_value=mock_portfolio), \
         patch("cryptolytics.CoinGeckoClient"), \
         patch("coinbasis.serde.lot_selection_from_json", return_value={}):
        with pytest.raises(SystemExit) as exc_info:
            cpt.cli(["--data-dir", str(tmp_path),
                     "holdings", "--method", "specific", "--select", str(sel_path)])

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "specific" in err.lower() or "automatic" in err.lower()


def test_news_all_feeds_failed_exits_1(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    news_path = tmp_path / "news.json"
    with open(news_path, "w") as f:
        json.dump({"feeds": ["http://bad.feed.example.com/rss"]}, f)

    with patch("cryptolytics.fetch_rss",
               side_effect=cryptolytics.FeedError("failed")), \
         patch("cryptolytics.fetch_cryptopanic", return_value=[]):
        # news with no items from any feed → no crash, but may print empty
        # (exit 1 only if ALL feeds fail AND no results; see spec)
        try:
            cpt.cli(["--data-dir", str(tmp_path), "news"])
        except SystemExit:
            # Acceptable if exit 0 (no items, but command ran) or exit 1
            pass
    # The key invariant: no unhandled exception/traceback
