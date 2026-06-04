"""Minimal guard: the 13 migrated modules must not exist; the packages must import."""

import importlib
import pytest


def test_migrated_modules_are_deleted():
    deleted = [
        "ledger", "costbasis", "holdings", "tax", "analytics",
        "rebalance", "backtest", "marketdata", "staking", "staking_api",
        "news", "news_source", "history",
    ]
    for name in deleted:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)


def test_packages_importable():
    import coinbasis          # noqa: F401
    import cryptolytics       # noqa: F401
