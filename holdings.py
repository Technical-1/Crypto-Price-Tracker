# holdings.py
import costbasis
import ledger


def derive_holdings(txns, method="fifo"):
    """Return {coin: {"total": qty, "cost": total_basis}} for coins still held,
    from the lots remaining after replaying the ledger."""
    _, remaining = costbasis.process_ledger(txns, method=method)
    result = {}
    for coin, lots in remaining.items():
        total = sum(l.quantity for l in lots)
        if total <= 1e-12:
            continue
        cost = sum(l.quantity * l.basis_per_unit for l in lots)
        result[coin] = {"total": total, "cost": cost}
    return result


def load_holdings_or_default(ledger_path, fallback, method="fifo"):
    """Derive holdings from the ledger if it has any transactions; otherwise
    return the fallback dict (the hardcoded originalHoldings)."""
    txns = ledger.load_ledger(ledger_path)
    if not txns:
        return fallback
    return derive_holdings(txns, method=method)
