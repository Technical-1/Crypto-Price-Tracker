# tests/test_staking_report.py
import staking_report


def test_format_yield_shows_apy_source_and_yield():
    rows = [
        {"coin": "ethereum", "apy": 0.05, "source": "api", "staked_qty": 2.0,
         "period_crypto": 0.1, "monthly_crypto": 0.00833, "period_usd": 300.0, "monthly_usd": 25.0},
    ]
    out = staking_report.format_yield(rows, days=365)
    assert "ethereum" in out
    assert "api" in out
    assert "5.0" in out          # apy percent
    assert "300.00" in out       # period usd


def test_format_rewards_shows_value_and_total():
    rows = [
        {"coin": "ethereum", "quantity": 0.03, "usd_value": 90.0},
        {"coin": "stellar", "quantity": 100.0, "usd_value": 10.0},
    ]
    out = staking_report.format_rewards(rows, 100.0)
    assert "ethereum" in out and "stellar" in out
    assert "90.00" in out
    assert "100.00" in out       # total


def test_format_comparison_shows_extra_income():
    rows = [{"coin": "ethereum", "extra_annual_usd": 300.0}]
    out = staking_report.format_comparison(rows, 300.0)
    assert "ethereum" in out
    assert "300.00" in out
    assert "not staked" in out.lower() or "vs" in out.lower()


def test_format_combined_pl_shows_three_figures():
    out = staking_report.format_combined_pl(500.0, 120.0, 620.0)
    assert "500.00" in out
    assert "120.00" in out
    assert "620.00" in out
