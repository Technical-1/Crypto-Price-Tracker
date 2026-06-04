"""Shared pytest fixtures for Phase 3 integration tests."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import coinlytics


# ── Helpers ────────────────────────────────────────────────────────────────────

def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


# ── Ledger fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def coinbasis_ledger_data():
    """A minimal coinbasis-schema ledger with one BTC buy + one ETH income."""
    return [
        {"Buy": {
            "timestamp": "2023-01-01T00:00:00Z",
            "wallet": "default",
            "asset": "bitcoin",
            "quantity": "1",
            "unit_price": "20000",
            "fee": "0",
        }},
        {"Income": {
            "timestamp": "2023-06-01T00:00:00Z",
            "wallet": "default",
            "asset": "ethereum",
            "quantity": "2",
            "value": "4000",
            "source": "Staking",
        }},
    ]


@pytest.fixture
def tmp_ledger(tmp_path, coinbasis_ledger_data):
    """Write coinbasis_ledger_data to tmp_path/ledger.json; return the path string."""
    path = tmp_path / "ledger.json"
    with open(path, "w") as f:
        json.dump(coinbasis_ledger_data, f)
    return str(path)


@pytest.fixture
def v1_ledger_data():
    """A V1-format flat ledger (2 rows: buy + sell)."""
    return [
        {"date": "2022-01-01", "coin": "bitcoin", "action": "buy",
         "quantity": 1.0, "price_usd": 45000.0, "fee_usd": 10.0},
        {"date": "2023-06-01", "coin": "bitcoin", "action": "sell",
         "quantity": 0.5, "price_usd": 30000.0, "fee_usd": 5.0},
    ]


@pytest.fixture
def tmp_v1_ledger(tmp_path, v1_ledger_data):
    """Write V1 flat ledger to tmp_path/ledger.json; return the path string."""
    path = tmp_path / "ledger.json"
    with open(path, "w") as f:
        json.dump(v1_ledger_data, f)
    return str(path)


# ── MockClient fixture ────────────────────────────────────────────────────────

@pytest.fixture
def mock_quotes():
    return {
        "bitcoin": coinlytics.Quote(
            price=Decimal("50000"),
            change_24h=Decimal("2.5"),
            change_7d=Decimal("5.0"),
            market_cap=Decimal("1000000000000"),
            volume_24h=Decimal("30000000000"),
        ),
        "ethereum": coinlytics.Quote(
            price=Decimal("3000"),
            change_24h=Decimal("-1.0"),
            change_7d=Decimal("3.0"),
            market_cap=Decimal("400000000000"),
            volume_24h=Decimal("15000000000"),
        ),
    }


@pytest.fixture
def mock_history():
    """10 daily points for BTC + ETH."""
    from datetime import date, timedelta
    today = date.today()
    return {
        "bitcoin": [
            coinlytics.HistoryPoint(
                date=(today - timedelta(days=9 - i)).isoformat(),
                price=float(45000 + i * 500),
            )
            for i in range(10)
        ],
        "ethereum": [
            coinlytics.HistoryPoint(
                date=(today - timedelta(days=9 - i)).isoformat(),
                price=float(2800 + i * 20),
            )
            for i in range(10)
        ],
    }


@pytest.fixture
def mock_market_caps():
    return {
        "bitcoin":  Decimal("1000000000000"),
        "ethereum": Decimal("400000000000"),
    }


@pytest.fixture
def mock_client(mock_quotes, mock_history, mock_market_caps):
    """A coinlytics.MockClient with BTC + ETH fixtures; no network calls."""
    return coinlytics.MockClient(
        quotes=mock_quotes,
        history=mock_history,
        market_caps=mock_market_caps,
        fail_ids=set(),
    )


@pytest.fixture
def failing_mock_client(mock_quotes, mock_history, mock_market_caps):
    """MockClient that raises PriceSourceError for 'bitcoin' (error-path tests)."""
    return coinlytics.MockClient(
        quotes=mock_quotes,
        history=mock_history,
        market_caps=mock_market_caps,
        fail_ids={"bitcoin"},
    )
