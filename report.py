# report.py
from decimal import Decimal
import coinbasis


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
