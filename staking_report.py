# staking_report.py


def format_yield(rows, days=365):
    """Current APY and projected yield per coin (crypto + USD)."""
    lines = ["Staking yield (projection over %d days):" % days,
             "      Coin        APY %   Source    Staked       Yield(crypto)   Yield(USD)   Monthly(USD)",
             "  ------------   ------   ------   ----------   -------------   ----------   ------------"]
    for r in rows:
        lines.append("  %-12s   %5.1f   %-6s   %10.4f   %13.6f   %10.2f   %12.2f" % (
            r["coin"], r["apy"] * 100, r["source"], r["staked_qty"],
            r["period_crypto"], r["period_usd"], r["monthly_usd"]))
    return "\n".join(lines)


def format_rewards(rows, total_usd):
    """Realized staking rewards per coin valued at the current price."""
    lines = ["Realized staking rewards:",
             "      Coin          Quantity      USD Value",
             "  ------------   -------------   ----------"]
    for r in rows:
        lines.append("  %-12s   %13.6f   %10.2f" % (r["coin"], r["quantity"], r["usd_value"]))
    lines.append("  Total reward value: %.2f USD" % total_usd)
    return "\n".join(lines)


def format_comparison(rows, total_extra_usd):
    """Staked vs not-staked: the extra annual income staking provides."""
    lines = ["Staked vs not staked (extra annual income):",
             "      Coin        Extra USD / yr",
             "  ------------   --------------"]
    for r in rows:
        lines.append("  %-12s   %14.2f" % (r["coin"], r["extra_annual_usd"]))
    lines.append("  Total extra income vs not staking: %.2f USD/yr" % total_extra_usd)
    return "\n".join(lines)


def format_combined_pl(portfolio_profit, rewards_value, combined):
    """Combined P/L: portfolio unrealized profit + realized-reward value."""
    return "\n".join([
        "Combined profit/loss:",
        "  Portfolio unrealized profit: %10.2f USD" % portfolio_profit,
        "  Realized staking rewards:    %10.2f USD" % rewards_value,
        "  Combined total:              %10.2f USD" % combined,
    ])
