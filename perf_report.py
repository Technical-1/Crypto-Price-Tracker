# perf_report.py
"""Performance view formatter: sparkline + PerfMetrics table."""
import cryptolytics
import chart as _chart


def format_performance(
    history: list[cryptolytics.Snapshot],
    metrics: cryptolytics.PerfMetrics,
) -> str:
    """Render a value sparkline and PerfMetrics.

    When all metric fields are None, renders a 'not enough history' notice
    (need at least 2 data points for returns / stats).
    """
    if not history:
        return "No performance history yet. Run any command to record a snapshot.\n"

    sorted_hist = sorted(history, key=lambda s: s.date)
    values = [s.total_value for s in sorted_hist]
    spark = _chart.sparkline(values)
    dates = f"{sorted_hist[0].date} → {sorted_hist[-1].date}"

    lines = [
        f"Performance  ({dates},  {len(history)} snapshots)",
        f"  Value: {spark}",
        f"  Now:   ${sorted_hist[-1].total_value:>12,.2f}   "
        f"P/L: ${sorted_hist[-1].pl:>+12,.2f}",
        "",
    ]

    if metrics.volatility is None and metrics.sharpe is None:
        lines.append("  (not enough history for statistics — record more snapshots)")
    else:
        vol_str = f"{metrics.volatility:.4f}" if metrics.volatility is not None else "N/A"
        shr_str = f"{metrics.sharpe:.2f}" if metrics.sharpe is not None else "N/A"
        mdd_str = f"{metrics.max_drawdown*100:.2f}%" if metrics.max_drawdown is not None else "N/A"
        cum_str = f"{metrics.cumulative_return*100:+.2f}%" if metrics.cumulative_return is not None else "N/A"
        lines += [
            f"  Volatility (daily):    {vol_str}",
            f"  Sharpe ratio:          {shr_str}",
            f"  Max drawdown:          {mdd_str}",
            f"  Cumulative return:     {cum_str}",
        ]

    return "\n".join(lines) + "\n"
