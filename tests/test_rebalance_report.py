# tests/test_rebalance_report.py
import rebalance_report


def test_format_allocation_shows_pct():
    current_values = {"bitcoin": 750.0, "ethereum": 250.0}
    out = rebalance_report.format_allocation(current_values)
    assert "bitcoin" in out and "ethereum" in out
    assert "75.0" in out and "25.0" in out


def test_format_risk_shows_per_coin_and_portfolio():
    vols_daily = {"bitcoin": 0.05, "ethereum": 0.08}
    vols_annual = {"bitcoin": 0.05 * 19.1, "ethereum": 0.08 * 19.1}
    out = rebalance_report.format_risk(vols_daily, vols_annual, 0.06)
    assert "bitcoin" in out and "ethereum" in out
    assert "Portfolio" in out


def test_format_correlation_renders_matrix():
    coins = ["bitcoin", "ethereum"]
    corr = {("bitcoin", "bitcoin"): 1.0, ("ethereum", "ethereum"): 1.0,
            ("bitcoin", "ethereum"): 0.42, ("ethereum", "bitcoin"): 0.42}
    out = rebalance_report.format_correlation(coins, corr)
    assert "bitcoin" in out and "ethereum" in out
    assert "0.42" in out


def test_format_trades_shows_actions():
    trades = [
        {"coin": "bitcoin", "action": "sell", "delta_usd": -200.0, "coin_amount": -0.004, "target_pct": 50.0},
        {"coin": "ethereum", "action": "buy", "delta_usd": 200.0, "coin_amount": 0.07, "target_pct": 50.0},
    ]
    out = rebalance_report.format_trades(trades)
    assert "sell" in out and "buy" in out
    assert "bitcoin" in out and "ethereum" in out


def test_format_backtest_shows_both_returns():
    out = rebalance_report.format_backtest(90, 0.12, 0.18, "equal")
    assert "90" in out
    assert "12.0" in out and "18.0" in out
    assert "equal" in out
