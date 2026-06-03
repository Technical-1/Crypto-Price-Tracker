# report.py


def format_realized(disposals):
    """Render realized disposals as a text table with short/long-term totals."""
    lines = ["Realized gains/losses:",
             "      Coin        Sell Date    Qty      Proceeds    Basis     Gain     Term",
             "  ------------   ----------   ------   ----------   ------   ------   ------"]
    short_total = long_total = 0.0
    for d in disposals:
        if d.term == "short":
            short_total += d.realized_gain
        else:
            long_total += d.realized_gain
        lines.append("  %-12s   %-10s   %6.3f   %10.2f   %6.2f   %6.2f   %-5s" % (
            d.coin, d.sell_date, d.quantity, d.proceeds, d.cost_basis,
            d.realized_gain, d.term))
    lines.append("  Short-term total: %.2f" % short_total)
    lines.append("  Long-term total:  %.2f" % long_total)
    return "\n".join(lines)


def format_unrealized(held, prices):
    """Render current holdings valued at live prices vs cost basis."""
    lines = ["Unrealized P/L (live prices):",
             "      Coin         Qty       Value      Basis     Unrealized",
             "  ------------   ------   ----------   ------   ------------"]
    for coin, h in held.items():
        coin_price = prices.get(coin)
        if not coin_price or coin_price.get("usd") is None:
            lines.append("  (skipped %s: no price data)" % coin)
            continue
        value = h["total"] * coin_price["usd"]
        unrealized = value - h["cost"]
        lines.append("  %-12s   %6.3f   %10.2f   %6.2f   %10.2f" % (
            coin, h["total"], value, h["cost"], unrealized))
    return "\n".join(lines)


def format_tax(short_gain, long_gain, short_tax, long_tax, config):
    """Render the estimated tax summary."""
    return "\n".join([
        "Estimated tax (%s):" % config.get("jurisdiction", "default"),
        "  Short-term gain: %10.2f   tax: %8.2f" % (short_gain, short_tax),
        "  Long-term gain:  %10.2f   tax: %8.2f" % (long_gain, long_tax),
        "  Total estimated tax: %.2f" % (short_tax + long_tax),
    ])
