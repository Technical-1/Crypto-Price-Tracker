# history_report.py
import chart


def format_chart(series):
    """Render value + P/L sparklines and a start/end/min/max/delta summary."""
    if not series:
        return "Portfolio history: (no data)"
    values = [p["value"] for p in series]
    pls = [p["pl"] for p in series]
    start, end = series[0], series[-1]
    lines = [
        "Portfolio history (%s to %s):" % (start["date"], end["date"]),
        "  Value  %s" % chart.sparkline(values),
        "  P/L    %s" % chart.sparkline(pls),
        "  Start: %.2f   End: %.2f   Min: %.2f   Max: %.2f   Delta: %.2f" % (
            start["value"], end["value"], min(values), max(values),
            end["value"] - start["value"]),
    ]
    return "\n".join(lines)


def format_playback(series, news_dates):
    """One line per day: date, value, pl, a P/L bar, and a '*' on news days."""
    if not series:
        return "Portfolio history: (no data)"
    max_abs = max((abs(p["pl"]) for p in series), default=0.0)
    lines = ["Playback:"]
    for p in series:
        marker = " *" if p["date"] in news_dates else ""
        lines.append("  %s  value %10.2f  pl %10.2f  %s%s" % (
            p["date"], p["value"], p["pl"], chart.hbar(p["pl"], max_abs, 20), marker))
    return "\n".join(lines)


def format_snapshot(date, rows, total_value, total_pl):
    """Per-coin breakdown for a single day with the day totals."""
    lines = [
        "Snapshot %s:" % date,
        "      Coin          Qty         Price        Value         P/L",
        "  ------------   ----------   ----------   ----------   ----------",
    ]
    for r in rows:
        lines.append("  %-12s   %10.4f   %10.2f   %10.2f   %10.2f" % (
            r["coin"], r["qty"], r["price"], r["value"], r["pl"]))
    lines.append("  Total value: %.2f   Total P/L: %.2f" % (total_value, total_pl))
    return "\n".join(lines)
