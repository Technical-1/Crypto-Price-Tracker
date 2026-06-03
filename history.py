import json

import holdings as holdings_mod


def holdings_as_of(txns, date, method="fifo"):
    """Holdings derived from only the transactions dated on or before `date`
    (ISO strings compare correctly). Returns {coin: {"total", "cost"}}."""
    upto = [t for t in txns if t.date <= date]
    return holdings_mod.derive_holdings(upto, method=method)


def reconstruct_series(txns, price_by_coin_date, dates, method="fifo"):
    """For each date (sorted), value the as-of holdings at that date's price.
    Coins lacking a price for a date are skipped for that day. Returns a list of
    {date, value, cost, pl}."""
    series = []
    for date in sorted(dates):
        held = holdings_as_of(txns, date, method=method)
        value = 0.0
        cost = 0.0
        for coin, h in held.items():
            price = price_by_coin_date.get(coin, {}).get(date)
            if price is None:
                continue
            value += h["total"] * price
            cost += h["cost"]
        series.append({"date": date, "value": value, "cost": cost, "pl": value - cost})
    return series


def make_snapshot(holdings, prices, date):
    """Build {date, total_value, cost, pl} from current holdings valued at live
    prices. Coins without a live usd price are skipped."""
    total_value = 0.0
    cost = 0.0
    for coin, h in holdings.items():
        price = (prices.get(coin) or {}).get("usd")
        if price is None:
            continue
        total_value += h["total"] * price
        cost += h["cost"]
    return {"date": date, "total_value": total_value, "cost": cost, "pl": total_value - cost}


def append_snapshot(path, snapshot):
    """Append one snapshot as a JSON line to the JSONL file."""
    with open(path, "a") as f:
        f.write(json.dumps(snapshot) + "\n")


def load_snapshots(path):
    """Read all snapshots from the JSONL file; missing file -> []."""
    try:
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []
