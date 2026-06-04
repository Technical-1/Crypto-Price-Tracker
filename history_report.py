# history_report.py
import chart as _chart
import cryptolytics


def format_chart(series: list[dict], news_markers: dict) -> str:
    """Render a sparkline of daily portfolio values."""
    if not series:
        return "No history data.\n"
    values = [pt["value"] for pt in series]
    spark = _chart.sparkline(values)
    lines = [f"Portfolio Value ({len(series)} days):", f"  {spark}"]
    for pt in series:
        marker = "*" if pt["date"] in news_markers else " "
        lines.append(
            f"  {marker} {pt['date']}  ${pt['value']:>10,.2f}  "
            f"P/L: ${pt['pl']:>+10,.2f}"
        )
    return "\n".join(lines) + "\n"


def format_playback(series: list[dict]) -> str:
    """Day-by-day playback view."""
    lines = ["Historical Playback"]
    for pt in series:
        lines.append(
            f"  {pt['date']}  value=${pt['value']:>10,.2f}  "
            f"cost=${pt['cost']:>10,.2f}  pl=${pt['pl']:>+10,.2f}"
        )
    return "\n".join(lines) + "\n"


def format_snapshot(snap: cryptolytics.Snapshot, rows: list[dict]) -> str:
    """Single-day snapshot detail view."""
    lines = [
        f"Snapshot: {snap.date}",
        f"  Total value: ${snap.total_value:>12,.2f}",
        f"  Cost:        ${snap.cost:>12,.2f}",
        f"  P/L:         ${snap.pl:>+12,.2f}",
        "",
        f"  {'Coin':<12} {'Qty':>10} {'Price':>12} {'Value':>12} {'P/L':>12}",
        "  " + "-" * 60,
    ]
    for r in rows:
        lines.append(
            f"  {r['coin']:<12} {float(r['qty']):>10.4f} {float(r['price']):>12.2f} "
            f"{float(r['value']):>12.2f} {float(r['pl']):>+12.2f}"
        )
    return "\n".join(lines) + "\n"
