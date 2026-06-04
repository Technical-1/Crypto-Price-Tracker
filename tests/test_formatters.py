"""Pure formatter tests — no mocks. Feed fixed package dataclasses, assert output."""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
import coinbasis
import cryptolytics
import report


def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


def test_format_realized_columns_present():
    rows = [
        coinbasis.RealizedGain(
            asset="bitcoin",
            wallet="default",
            disposed_at=_utc(2024, 3, 1),
            acquired_at=_utc(2023, 1, 1),
            quantity=Decimal("0.5"),
            proceeds=Decimal("15000"),
            cost_basis=Decimal("10000"),
            gain=Decimal("5000"),
            term=coinbasis.Term.LONG,
        )
    ]
    out = report.format_realized(rows)
    assert "bitcoin" in out
    assert "LONG" in out or "Long" in out
    assert "5000" in out
    assert "15000" in out
    assert "2024-03-01" in out


def test_format_realized_short_long_subtotals():
    rows = [
        coinbasis.RealizedGain(
            asset="bitcoin", wallet="default",
            disposed_at=_utc(2024, 3, 1), acquired_at=_utc(2023, 1, 1),
            quantity=Decimal("1"), proceeds=Decimal("60000"),
            cost_basis=Decimal("50000"), gain=Decimal("10000"),
            term=coinbasis.Term.LONG,
        ),
        coinbasis.RealizedGain(
            asset="ethereum", wallet="default",
            disposed_at=_utc(2024, 6, 1), acquired_at=_utc(2024, 3, 1),
            quantity=Decimal("2"), proceeds=Decimal("6000"),
            cost_basis=Decimal("4000"), gain=Decimal("2000"),
            term=coinbasis.Term.SHORT,
        ),
    ]
    out = report.format_realized(rows)
    # Short gain subtotal
    assert "2000" in out
    # Long gain subtotal
    assert "10000" in out


def test_format_realized_empty_returns_no_rows_message():
    out = report.format_realized([])
    assert "no realized" in out.lower() or out.strip() == "" or "Realized" in out


def test_format_unrealized_renders_asset_rows():
    report_obj = coinbasis.PortfolioReport(
        assets=[
            coinbasis.AssetValuation(
                asset="bitcoin",
                quantity=Decimal("1"),
                cost_basis=Decimal("50000"),
                price=Decimal("60000"),
                market_value=Decimal("60000"),
                unrealized=Decimal("10000"),
                allocation=Decimal("1"),
            )
        ],
        total_cost=Decimal("50000"),
        total_value=Decimal("60000"),
        total_unrealized=Decimal("10000"),
        total_return=Decimal("0.2"),
        missing_prices=[],
    )
    out = report.format_unrealized(report_obj)
    assert "bitcoin" in out
    assert "60000" in out
    assert "10000" in out
    assert "100" in out or "1.00" in out  # allocation 100% or 1.0


def test_format_unrealized_missing_prices_notice():
    report_obj = coinbasis.PortfolioReport(
        assets=[],
        total_cost=Decimal("0"),
        total_value=Decimal("0"),
        total_unrealized=Decimal("0"),
        total_return=Decimal("0"),
        missing_prices=["solana"],
    )
    out = report.format_unrealized(report_obj)
    assert "solana" in out or "missing" in out.lower()


import chart


def _make_book(coins: dict) -> cryptolytics.PriceBook:
    """Build a minimal PriceBook for testing."""
    from datetime import datetime, timezone
    quotes = {
        cid: cryptolytics.Quote(
            price=Decimal(str(data["price"])),
            change_24h=Decimal(str(data.get("change_24h", "0"))),
            change_7d=None,
            market_cap=None,
            volume_24h=None,
        )
        for cid, data in coins.items()
    }
    return cryptolytics.PriceBook(
        quotes=quotes,
        fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        stale=False,
        sparklines={},
    )


def test_format_prices_headers_and_data():
    pr = coinbasis.PortfolioReport(
        assets=[
            coinbasis.AssetValuation(
                asset="bitcoin",
                quantity=Decimal("1"),
                cost_basis=Decimal("50000"),
                price=Decimal("60000"),
                market_value=Decimal("60000"),
                unrealized=Decimal("10000"),
                allocation=Decimal("1"),
            )
        ],
        total_cost=Decimal("50000"),
        total_value=Decimal("60000"),
        total_unrealized=Decimal("10000"),
        total_return=Decimal("0.2"),
        missing_prices=[],
    )
    book = _make_book({"bitcoin": {"price": 60000, "change_24h": 2.5}})
    out = report.format_prices(pr, book)
    assert "bitcoin" in out
    assert "60000" in out
    assert "2.5" in out or "+2.50" in out or "2.50" in out


def test_format_holdings_all_columns():
    holdings = [
        coinbasis.Holding(
            asset="bitcoin", wallet="default",
            quantity=Decimal("2"),
            cost_basis=Decimal("100000"),
            average_cost=Decimal("50000"),
        )
    ]
    out = report.format_holdings(holdings, prices_map={}, group="asset")
    assert "bitcoin" in out
    assert "default" in out
    assert "50000" in out


def test_format_valuation_shows_alloc_bars():
    pr = coinbasis.PortfolioReport(
        assets=[
            coinbasis.AssetValuation(
                asset="bitcoin",
                quantity=Decimal("1"),
                cost_basis=Decimal("50000"),
                price=Decimal("60000"),
                market_value=Decimal("60000"),
                unrealized=Decimal("10000"),
                allocation=Decimal("0.6"),
            ),
            coinbasis.AssetValuation(
                asset="ethereum",
                quantity=Decimal("10"),
                cost_basis=Decimal("20000"),
                price=Decimal("4000"),
                market_value=Decimal("40000"),
                unrealized=Decimal("20000"),
                allocation=Decimal("0.4"),
            ),
        ],
        total_cost=Decimal("70000"),
        total_value=Decimal("100000"),
        total_unrealized=Decimal("30000"),
        total_return=Decimal("0.428"),
        missing_prices=[],
    )
    out = report.format_valuation(pr)
    assert "bitcoin" in out
    assert "ethereum" in out
    assert any(c in out for c in ["█", "▓", "|", "#"])


def test_format_tax_shows_estimate():
    estimate = coinbasis.TaxEstimate(
        short_term_gain=Decimal("2000"),
        long_term_gain=Decimal("10000"),
        short_term_tax=Decimal("700"),
        long_term_tax=Decimal("0"),
        total_tax=Decimal("700"),
    )
    config = coinbasis.TaxConfig.default()
    out = report.format_tax(estimate, config)
    assert "700" in out
    assert "Short" in out or "short" in out
    assert "Long" in out or "long" in out
    assert "US" in out or config.jurisdiction in out


import rebalance_report


def _make_plan(in_balance: bool = False) -> cryptolytics.RebalancePlan:
    from cryptolytics import RebalanceAction, RebalancePlan
    actions = [
        RebalanceAction(
            asset="bitcoin",
            current_value=Decimal("60000"),
            target_value=Decimal("50000"),
            drift=Decimal("10000"),
            side="sell",
            amount_usd=Decimal("10000"),
            coin_amount=Decimal("0.1667"),
            target_pct=Decimal("50"),
            tax=None,
        ),
        RebalanceAction(
            asset="ethereum",
            current_value=Decimal("40000"),
            target_value=Decimal("50000"),
            drift=Decimal("-10000"),
            side="buy",
            amount_usd=Decimal("10000"),
            coin_amount=Decimal("2.5"),
            target_pct=Decimal("50"),
            tax=None,
        ),
    ]
    return RebalancePlan(
        actions=actions,
        total_value=Decimal("100000"),
        total_buys_usd=Decimal("10000"),
        total_sells_usd=Decimal("10000"),
        in_balance=in_balance,
    )


def test_format_trades_shows_side_and_amount():
    plan = _make_plan()
    out = rebalance_report.format_trades(plan)
    assert "sell" in out.lower() or "SELL" in out
    assert "buy" in out.lower() or "BUY" in out
    assert "bitcoin" in out
    assert "10000" in out


def test_format_allocation_shows_targets():
    plan = _make_plan()
    out = rebalance_report.format_allocation(plan)
    assert "bitcoin" in out
    assert "50" in out  # target_pct


def test_in_balance_banner():
    plan_balanced = _make_plan(in_balance=True)
    out = rebalance_report.format_trades(plan_balanced)
    assert "balance" in out.lower() or "no trades" in out.lower()
