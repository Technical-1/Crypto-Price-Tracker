import json

import holdings as holdings_mod


def holdings_as_of(txns, date, method="fifo"):
    """Holdings derived from only the transactions dated on or before `date`
    (ISO strings compare correctly). Returns {coin: {"total", "cost"}}."""
    upto = [t for t in txns if t.date <= date]
    return holdings_mod.derive_holdings(upto, method=method)
