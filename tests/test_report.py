# tests/test_report.py
import report
from costbasis import Disposal


def test_format_realized_shows_totals_and_terms():
    disposals = [
        Disposal("bitcoin", "2024-05-01", 1.0, 150.0, 100.0, 50.0, 120, "short"),
        Disposal("ethereum", "2024-06-01", 2.0, 400.0, 300.0, 100.0, 400, "long"),
    ]
    out = report.format_realized(disposals)
    assert "bitcoin" in out and "ethereum" in out
    assert "Short-term total" in out
    assert "50.00" in out and "100.00" in out


def test_format_unrealized_uses_live_prices():
    held = {"bitcoin": {"total": 1.0, "cost": 100.0}}
    prices = {"bitcoin": {"usd": 150.0}}
    out = report.format_unrealized(held, prices)
    assert "bitcoin" in out
    assert "50.00" in out  # 150 value - 100 basis


def test_format_tax_names_jurisdiction():
    cfg = {"jurisdiction": "US", "short_term_rate": 0.35,
           "long_term_brackets": [{"up_to": None, "rate": 0.15}]}
    out = report.format_tax(100.0, 200.0, 35.0, 30.0, cfg)
    assert "US" in out
    assert "35.00" in out and "30.00" in out
    assert "65.00" in out  # total
