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
    Lots still held per coin. method ∈ {fifo, lifo, average}."""
    lots = {}      # coin -> list[Lot]
    disposals = []
    ordered = sorted(txns, key=lambda t: t.date)

    for t in ordered:
        bucket = lots.setdefault(t.coin, [])
        if t.action == "buy":
            basis_per_unit = (t.price_usd + t.fee_usd) / t.quantity
            bucket.append(Lot(t.date, t.quantity, basis_per_unit))
            continue

        # sell
        remaining_to_sell = t.quantity
        held = sum(l.quantity for l in bucket)
        if t.quantity > held + 1e-12:
            print(f"  (warning {t.coin} {t.date}: sell of {t.quantity} exceeds "
                  f"held {held}; selling only {held})", file=sys.stderr)
            remaining_to_sell = held

        while remaining_to_sell > 1e-12 and bucket:
            lot = bucket[0] if method != "lifo" else bucket[-1]
            take = min(lot.quantity, remaining_to_sell)
            fee_share = t.fee_usd * (take / t.quantity)
            proceeds = take * t.price_usd - fee_share
            basis_per_unit = _basis_for(method, lot, bucket)
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
                bucket.remove(lot)

    return disposals, {c: ls for c, ls in lots.items()}


def _basis_for(method, lot, bucket):
    if method == "average":
        total_qty = sum(l.quantity for l in bucket)
        total_basis = sum(l.quantity * l.basis_per_unit for l in bucket)
        return total_basis / total_qty if total_qty else lot.basis_per_unit
    return lot.basis_per_unit
