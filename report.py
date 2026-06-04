# report.py
from decimal import Decimal
import coinbasis
import cryptolytics
import chart as _chart


def format_realized(rows: list[coinbasis.RealizedGain]) -> str:
    """Render a table of RealizedGain rows with short/long subtotals."""
    if not rows:
        return "Realized gains: (none)\n"

    lines = []
    header = (
        f"{'Asset':<12} {'Wallet':<10} {'Acquired':<12} {'Disposed':<12} "
        f"{'Qty':>10} {'Proceeds':>12} {'Basis':>12} {'Gain':>12} {'Term':<6}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    short_gain = Decimal("0")
    long_gain = Decimal("0")
    other_gain = Decimal("0")

    for r in rows:
        acq = r.acquired_at.strftime("%Y-%m-%d") if r.acquired_at else "N/A"
        dis = r.disposed_at.strftime("%Y-%m-%d")
        term_str = r.term.value if r.term else "N/A"

        line = (
            f"{r.asset:<12} {r.wallet:<10} {acq:<12} {dis:<12} "
            f"{float(r.quantity):>10.4f} {float(r.proceeds):>12.2f} "
            f"{float(r.cost_basis):>12.2f} {float(r.gain):>12.2f} {term_str:<6}"
        )
        lines.append(line)

        if r.term == coinbasis.Term.SHORT:
            short_gain += r.gain
        elif r.term == coinbasis.Term.LONG:
            long_gain += r.gain
        else:
            other_gain += r.gain

    lines.append("-" * len(header))
    if short_gain:
        lines.append(f"  Short-term gain: ${float(short_gain):>12.2f}")
    if long_gain:
        lines.append(f"  Long-term gain:  ${float(long_gain):>12.2f}")
    if other_gain:
        lines.append(f"  Other gain:      ${float(other_gain):>12.2f}")
    total = short_gain + long_gain + other_gain
    lines.append(f"  Total gain:      ${float(total):>12.2f}")
    return "\n".join(lines) + "\n"


def format_unrealized(portfolio_report: coinbasis.PortfolioReport) -> str:
    """Render unrealized P/L from a coinbasis PortfolioReport."""
    lines = ["Unrealized P/L"]
    header = (
        f"{'Asset':<12} {'Qty':>10} {'Cost Basis':>12} "
        f"{'Market Val':>12} {'Unrealized':>12} {'Alloc':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    for av in portfolio_report.assets:
        alloc_pct = float(av.allocation) * 100
        line = (
            f"{av.asset:<12} {float(av.quantity):>10.4f} "
            f"{float(av.cost_basis):>12.2f} {float(av.market_value):>12.2f} "
            f"{float(av.unrealized):>12.2f} {alloc_pct:>7.1f}%"
        )
        lines.append(line)

    lines.append("-" * len(header))
    lines.append(
        f"{'Total':<12} {'':>10} {float(portfolio_report.total_cost):>12.2f} "
        f"{float(portfolio_report.total_value):>12.2f} "
        f"{float(portfolio_report.total_unrealized):>12.2f} {'':>8}"
    )
    ret_pct = float(portfolio_report.total_return) * 100
    lines.append(f"  Total return: {ret_pct:+.2f}%")

    if portfolio_report.missing_prices:
        missing_str = ", ".join(portfolio_report.missing_prices)
        lines.append(f"  (no price data for: {missing_str})")

    return "\n".join(lines) + "\n"


def format_prices(
    portfolio_report: coinbasis.PortfolioReport,
    book: "cryptolytics.PriceBook",
    sparklines: dict[str, list[float]] | None = None,
) -> str:
    """Prices view (V2 view 1): COIN · PRICE · 24H% · 7D% · HELD · COST · VALUE · PROFIT · ALLOC%."""
    spark_map = sparklines if sparklines is not None else book.sparklines
    lines = []
    header = (
        f"{'Coin':<16} {'Price':>12} {'24h%':>8} {'7d%':>8} "
        f"{'Held':>10} {'Cost':>12} {'Value':>12} {'Profit':>12} {'Alloc':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    for av in portfolio_report.assets:
        q = book.quotes.get(av.asset)
        c24 = float(q.change_24h) if q and q.change_24h is not None else 0.0
        c7 = float(q.change_7d) if q and q.change_7d is not None else 0.0
        spark = spark_map.get(av.asset, [])
        spark_str = " " + _chart.sparkline(spark) if spark else ""
        alloc_pct = float(av.allocation) * 100
        line = (
            f"{av.asset:<16} {float(av.price):>12.2f} {c24:>+8.2f}% {c7:>+7.2f}% "
            f"{float(av.quantity):>10.4f} {float(av.cost_basis):>12.2f} "
            f"{float(av.market_value):>12.2f} {float(av.unrealized):>+12.2f} "
            f"{alloc_pct:>7.1f}%{spark_str}"
        )
        lines.append(line)

    lines.append("-" * len(header))
    total_profit = portfolio_report.total_unrealized
    lines.append(
        f"{'Total':<16} {'':>12} {'':>8} {'':>8} {'':>10} "
        f"{float(portfolio_report.total_cost):>12.2f} "
        f"{float(portfolio_report.total_value):>12.2f} "
        f"{float(total_profit):>+12.2f} {'':>8}"
    )

    if portfolio_report.missing_prices:
        lines.append(f"  (no price for: {', '.join(portfolio_report.missing_prices)})")

    return "\n".join(lines) + "\n"


def format_holdings(
    holdings: list[coinbasis.Holding],
    prices_map: dict,
    group: str = "asset",
) -> str:
    """Holdings view: ASSET · WALLET · QTY · COST · AVG COST [· VALUE · UNREALIZED]."""
    lines = []
    has_prices = bool(prices_map)
    header = (
        f"{'Asset':<12} {'Wallet':<12} {'Qty':>12} {'Cost Basis':>12} {'Avg Cost':>12}"
        + (f" {'Value':>12} {'Unrealized':>12}" if has_prices else "")
    )
    lines.append(header)
    lines.append("-" * len(header))

    # Optionally group by asset, merging wallets
    if group == "asset":
        merged: dict[str, coinbasis.Holding] = {}
        wallets: dict[str, set] = {}
        for h in holdings:
            wallets.setdefault(h.asset, set()).add(h.wallet)
            if h.asset in merged:
                m = merged[h.asset]
                merged[h.asset] = coinbasis.Holding(
                    asset=m.asset, wallet=m.wallet,
                    quantity=m.quantity + h.quantity,
                    cost_basis=m.cost_basis + h.cost_basis,
                    average_cost=(m.cost_basis + h.cost_basis) / (m.quantity + h.quantity),
                )
            else:
                merged[h.asset] = coinbasis.Holding(
                    asset=h.asset, wallet=h.wallet,
                    quantity=h.quantity, cost_basis=h.cost_basis,
                    average_cost=h.average_cost,
                )
        display_holdings = []
        for asset, m in merged.items():
            label = m.wallet if len(wallets[asset]) == 1 else "(all)"
            display_holdings.append(
                coinbasis.Holding(
                    asset=m.asset, wallet=label,
                    quantity=m.quantity, cost_basis=m.cost_basis,
                    average_cost=m.average_cost,
                )
            )
    else:
        display_holdings = holdings

    for h in display_holdings:
        price = Decimal(str(prices_map.get(h.asset, 0)))
        value = h.quantity * price if price else Decimal(0)
        unrealized = value - h.cost_basis if price else Decimal(0)
        row = (
            f"{h.asset:<12} {h.wallet:<12} {float(h.quantity):>12.6f} "
            f"{float(h.cost_basis):>12.2f} {float(h.average_cost):>12.2f}"
        )
        if has_prices:
            row += f" {float(value):>12.2f} {float(unrealized):>+12.2f}"
        lines.append(row)

    lines.append("-" * len(header))
    return "\n".join(lines) + "\n"


def format_valuation(portfolio_report: coinbasis.PortfolioReport) -> str:
    """Valuation view: headline totals + per-asset allocation bars."""
    lines = [
        "Portfolio Valuation",
        f"  Total cost:       ${float(portfolio_report.total_cost):>14.2f}",
        f"  Total value:      ${float(portfolio_report.total_value):>14.2f}",
        f"  Unrealized P/L:   ${float(portfolio_report.total_unrealized):>+14.2f}",
        f"  Total return:     {float(portfolio_report.total_return)*100:>+.2f}%",
        "",
        "Asset Allocation",
    ]
    max_alloc = max(
        (float(av.allocation) for av in portfolio_report.assets),
        default=1.0,
    ) or 1.0
    bar_width = 30
    for av in portfolio_report.assets:
        alloc = float(av.allocation)
        bar = _chart.hbar(alloc, max_alloc, bar_width)
        lines.append(f"  {av.asset:<12} {bar} {alloc*100:5.1f}%  ${float(av.market_value):>12.2f}")

    if portfolio_report.missing_prices:
        lines.append(f"\n  (no price for: {', '.join(portfolio_report.missing_prices)})")

    return "\n".join(lines) + "\n"


def format_tax(estimate: coinbasis.TaxEstimate, config: coinbasis.TaxConfig) -> str:
    """Render a TaxEstimate + TaxConfig into a tax summary string."""
    lines = [
        f"Estimated Tax ({config.jurisdiction})",
        f"  Short-term gain:  ${float(estimate.short_term_gain):>12,.2f}  "
        f"@ {float(config.short_term_rate)*100:.0f}%  "
        f"→ ${float(estimate.short_term_tax):>10,.2f}",
        f"  Long-term gain:   ${float(estimate.long_term_gain):>12,.2f}  "
        f"(brackets)         → ${float(estimate.long_term_tax):>10,.2f}",
        f"  {'─'*60}",
        f"  Total estimated tax:            ${float(estimate.total_tax):>10,.2f}",
    ]
    return "\n".join(lines) + "\n"
