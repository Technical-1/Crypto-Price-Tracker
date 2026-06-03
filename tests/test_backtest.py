import math
import backtest


def test_buy_and_hold_return_two_coins():
    # a: 100 -> 150 (+50%); b: 200 -> 200 (0%); weights 0.5/0.5
    history = {
        "a": [("2024-01-01", 100.0), ("2024-02-01", 120.0), ("2024-03-01", 150.0)],
        "b": [("2024-01-01", 200.0), ("2024-03-01", 200.0)],
    }
    weights = {"a": 0.5, "b": 0.5}
    # 0.5*0.5 + 0.5*0.0 = 0.25
    assert math.isclose(backtest.buy_and_hold_return(history, weights), 0.25, rel_tol=1e-9)


def test_buy_and_hold_skips_missing_history_and_renormalizes():
    # b has no history -> drop b, renormalize to a only -> a return only (+50%)
    history = {"a": [("2024-01-01", 100.0), ("2024-03-01", 150.0)]}
    weights = {"a": 0.5, "b": 0.5}
    assert math.isclose(backtest.buy_and_hold_return(history, weights), 0.5, rel_tol=1e-9)


def test_buy_and_hold_empty_returns_zero():
    assert backtest.buy_and_hold_return({}, {"a": 1.0}) == 0.0
