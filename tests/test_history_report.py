# tests/test_history_report.py
import history_report


SERIES = [
    {"date": "2024-01-01", "value": 200.0, "cost": 200.0, "pl": 0.0},
    {"date": "2024-01-02", "value": 300.0, "cost": 200.0, "pl": 100.0},
    {"date": "2024-01-03", "value": 250.0, "cost": 200.0, "pl": 50.0},
]


def test_format_chart_shows_sparklines_and_summary():
    out = history_report.format_chart(SERIES)
    assert "Value" in out
    assert "P/L" in out or "P&L" in out
    assert "2024-01-01" in out and "2024-01-03" in out   # start / end dates
    assert "300.00" in out                                # max value in summary


def test_format_chart_empty_series():
    out = history_report.format_chart([])
    assert "no" in out.lower()


def test_format_playback_marks_news_days():
    out = history_report.format_playback(SERIES, {"2024-01-02"})
    assert "2024-01-01" in out and "2024-01-02" in out and "2024-01-03" in out
    # the news day line carries a marker
    news_line = [ln for ln in out.splitlines() if "2024-01-02" in ln][0]
    assert "*" in news_line
    plain_line = [ln for ln in out.splitlines() if "2024-01-01" in ln][0]
    assert "*" not in plain_line


def test_format_snapshot_shows_rows_and_totals():
    rows = [
        {"coin": "bitcoin", "qty": 1.0, "price": 200.0, "value": 200.0, "pl": 100.0},
        {"coin": "ethereum", "qty": 10.0, "price": 10.0, "value": 100.0, "pl": 50.0},
    ]
    out = history_report.format_snapshot("2024-01-02", rows, 300.0, 150.0)
    assert "2024-01-02" in out
    assert "bitcoin" in out and "ethereum" in out
    assert "300.00" in out and "150.00" in out
