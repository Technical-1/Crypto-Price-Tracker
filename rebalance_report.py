# rebalance_report.py
import coinlytics


def format_trades(plan: coinlytics.RebalancePlan) -> str:
    if plan.in_balance:
        return "Portfolio is in balance. No trades needed.\n"
    lines = ["Proposed Trades"]
    header = f"{'Side':<6} {'Asset':<14} {'Amount USD':>12} {'Qty':>12} {'Drift%':>8} {'Est.Gain':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for a in plan.actions:
        if a.side == "hold":
            continue
        if a.tax is not None:
            gain_str = f"{float(a.tax.realized_gain):>+12.2f}"
        else:
            gain_str = f"{'N/A':>12}"
        drift_pct = float(a.drift) / float(plan.total_value) * 100 if plan.total_value else 0
        lines.append(
            f"{a.side.upper():<6} {a.asset:<14} {float(a.amount_usd):>12.2f} "
            f"{float(a.coin_amount):>12.4f} {drift_pct:>+7.2f}% {gain_str}"
        )
    lines.append("-" * len(header))
    lines.append(
        f"  Buys:  ${float(plan.total_buys_usd):>10,.2f}   "
        f"Sells: ${float(plan.total_sells_usd):>10,.2f}"
    )
    return "\n".join(lines) + "\n"


def format_allocation(plan: coinlytics.RebalancePlan) -> str:
    lines = ["Current vs Target Allocation"]
    header = f"{'Asset':<14} {'Current':>12} {'Target':>12} {'Target%':>8} {'Drift':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for a in plan.actions:
        lines.append(
            f"{a.asset:<14} {float(a.current_value):>12.2f} "
            f"{float(a.target_value):>12.2f} {float(a.target_pct):>7.1f}% "
            f"{float(a.drift):>+12.2f}"
        )
    return "\n".join(lines) + "\n"


def format_risk(vol_by_coin: dict, port_vol: float, ann_port_vol: float) -> str:
    lines = ["Risk Analytics"]
    for coin, vol in vol_by_coin.items():
        lines.append(f"  {coin:<14} daily vol: {vol:.4f}  annualized: {vol * (365**0.5):.4f}")
    lines.append(f"  Portfolio volatility (daily): {port_vol:.4f}  annualized: {ann_port_vol:.4f}")
    return "\n".join(lines) + "\n"


def format_backtest(bah_return: float, target_return: float, days: int) -> str:
    return (
        f"Backtest ({days}d): buy-and-hold = {bah_return*100:+.2f}%  "
        f"rebalanced = {target_return*100:+.2f}%\n"
    )


def format_correlation(corr: dict, coins: list) -> str:
    lines = ["Correlation Matrix"]
    lines.append("        " + "".join(f"{c:>10}" for c in coins))
    for a in coins:
        row = f"{a:<8}" + "".join(f"{corr.get((a,b), corr.get((b,a), 1.0)):>10.2f}" for b in coins)
        lines.append(row)
    return "\n".join(lines) + "\n"
