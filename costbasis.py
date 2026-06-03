# costbasis.py
import sys
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Lot:
    date: str            # acquisition date, ISO
    quantity: float
    basis_per_unit: float  # includes allocated buy fee


@dataclass
class Disposal:
    coin: str
    sell_date: str
    quantity: float
    proceeds: float
    cost_basis: float
    realized_gain: float
    holding_days: int
    term: str            # "short" or "long"


def _days(acquired, sold):
    a = datetime.strptime(acquired, "%Y-%m-%d")
    s = datetime.strptime(sold, "%Y-%m-%d")
    return (s - a).days


def process_ledger(txns, method="fifo", long_term_threshold=365):
    """Replay transactions chronologically, producing realized Disposals and the
    Lots still held per coin. method in {fifo, lifo, average}.
    Precondition: txns are already validated (e.g. via ledger.load_ledger), so
    dates are ISO and quantities/prices are numeric."""
    if method not in {"fifo", "lifo", "average"}:
        raise ValueError(f"unknown cost-basis method {method!r}")

    lots = {}      # coin -> list[Lot]
    disposals = []
    ordered = sorted(txns, key=lambda t: t.date)

    for t in ordered:
        bucket = lots.setdefault(t.coin, [])
        if t.action == "buy":
            basis_per_unit = (t.price_usd * t.quantity + t.fee_usd) / t.quantity
            bucket.append(Lot(t.date, t.quantity, basis_per_unit))
            continue

        # sell
        held = sum(l.quantity for l in bucket)
        sell_qty = t.quantity
        if sell_qty > held + 1e-12:
            print(f"  (warning {t.coin} {t.date}: sell of {t.quantity} exceeds "
                  f"held {held}; selling only {held})", file=sys.stderr)
            sell_qty = held

        # Average cost: snapshot the pooled per-unit basis once, over the
        # pre-sell pool, so every slice of this sell uses the same average.
        pooled_avg = None
        if method == "average" and held > 0:
            pooled_avg = sum(l.quantity * l.basis_per_unit for l in bucket) / held

        remaining_to_sell = sell_qty
        while remaining_to_sell > 1e-12 and bucket:
            lot = bucket[-1] if method == "lifo" else bucket[0]
            take = min(lot.quantity, remaining_to_sell)
            fee_share = t.fee_usd * (take / sell_qty) if sell_qty else 0.0
            proceeds = take * t.price_usd - fee_share
            basis_per_unit = pooled_avg if method == "average" else lot.basis_per_unit
            cost_basis = take * basis_per_unit
            holding_days = _days(lot.date, t.date)
            disposals.append(Disposal(
                coin=t.coin, sell_date=t.date, quantity=take,
                proceeds=proceeds, cost_basis=cost_basis,
                realized_gain=proceeds - cost_basis,
                holding_days=holding_days,
                term="short" if holding_days <= long_term_threshold else "long",
            ))
            lot.quantity -= take
            remaining_to_sell -= take
            if lot.quantity <= 1e-12:
                if method == "lifo":
                    bucket.pop()
                else:
                    bucket.pop(0)

    return disposals, {c: [Lot(l.date, l.quantity, l.basis_per_unit) for l in ls]
                       for c, ls in lots.items()}
