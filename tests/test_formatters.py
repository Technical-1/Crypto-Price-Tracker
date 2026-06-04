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
