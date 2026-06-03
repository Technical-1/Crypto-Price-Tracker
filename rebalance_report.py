# rebalance_report.py


def format_allocation(current_values):
    """Current allocation table: coin, USD value, percent of portfolio."""
    total = sum(current_values.values())
    lines = ["Current allocation:",
             "      Coin          Value       %",
             "  ------------   ----------   ------"]
    for coin in sorted(current_values, key=lambda c: -current_values[c]):
        value = current_values[coin]
        pct = (value / total * 100) if total else 0.0
        lines.append("  %-12s   %10.2f   %5.1f" % (coin, value, pct))
    return "\n".join(lines)


def format_risk(vols_daily, vols_annual, portfolio_vol=None):
    """Per-coin daily/annualized volatility plus the portfolio volatility.

    When portfolio_vol is None (fewer than two coins have history), the
    portfolio volatility line is omitted entirely.
    """
    lines = ["Risk (volatility):",
             "      Coin         Daily %    Annual %",
             "  ------------   --------   ---------"]
    for coin in sorted(vols_daily):
        lines.append("  %-12s   %7.2f   %8.2f" % (
            coin, vols_daily[coin] * 100, vols_annual.get(coin, 0.0) * 100))
    if portfolio_vol is not None:
        lines.append("  Portfolio daily volatility: %.2f%%" % (portfolio_vol * 100))
    return "\n".join(lines)


def format_correlation(coins, corr):
    """Labeled correlation matrix among coins."""
    lines = ["Correlation matrix:"]
    header = "  %-12s" % "" + "".join("%10s" % c[:9] for c in coins)
    lines.append(header)
    for a in coins:
        row = "  %-12s" % a[:12] + "".join(
            "%10.2f" % corr.get((a, b), 0.0) for b in coins)
        lines.append(row)
    return "\n".join(lines)


def format_trades(trades):
    """Rebalancing trades: coin, action, USD delta, coin amount, target %."""
    lines = ["Rebalancing trades:",
             "      Coin        Action     Delta USD     Coin Amount    Target %",
             "  ------------   --------   -----------   -------------   --------"]
    for t in trades:
        lines.append("  %-12s   %-8s   %11.2f   %13.6f   %7.1f" % (
            t["coin"], t["action"], t["delta_usd"], t["coin_amount"], t["target_pct"]))
    return "\n".join(lines)


def format_backtest(window_days, current_return, target_return, strategy):
    """Window buy-and-hold return: current weights vs target strategy."""
    return "\n".join([
        "Backtest (last %d days, buy & hold):" % window_days,
        "  Current allocation return: %6.1f%%" % (current_return * 100),
        "  Target (%s) return:        %6.1f%%" % (strategy, target_return * 100),
    ])
