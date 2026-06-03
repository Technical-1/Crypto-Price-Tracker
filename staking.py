import csv
import json
import sys


def load_config(path):
    """Load staking config {coin: {staked_qty, symbol?, apy?}}. Raises ValueError
    if missing, malformed, not an object, or any entry lacks a positive
    staked_qty."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"staking config not found: {path}")
    except json.JSONDecodeError as err:
        raise ValueError(f"staking config is not valid JSON: {err}")
    if not isinstance(data, dict) or not data:
        raise ValueError("staking config must be a non-empty object")
    for coin, entry in data.items():
        qty = entry.get("staked_qty") if isinstance(entry, dict) else None
        if not isinstance(qty, (int, float)) or qty <= 0:
            raise ValueError(f"{coin}: staked_qty must be a positive number")
    return data


def load_rewards(path):
    """Load realized rewards from a CSV (date,coin,quantity). Missing file -> [].
    Rows with an invalid quantity or empty coin are skipped with a stderr notice."""
    try:
        f = open(path, newline="")
    except FileNotFoundError:
        return []
    rewards = []
    with f:
        for lineno, row in enumerate(csv.DictReader(f), start=2):
            coin = (row.get("coin") or "").strip()
            try:
                qty = float(row["quantity"])
            except (KeyError, TypeError, ValueError):
                print(f"  (skipped rewards line {lineno}: invalid quantity)", file=sys.stderr)
                continue
            if not coin:
                print(f"  (skipped rewards line {lineno}: missing coin)", file=sys.stderr)
                continue
            rewards.append({"date": (row.get("date") or "").strip(), "coin": coin, "quantity": qty})
    return rewards


def effective_apys(config, api_apys):
    """Return {coin: (apy, source)}. Prefer the API APY (matched by the coin's
    configured symbol), else the manual 'apy' in config; omit coins with neither."""
    result = {}
    for coin, entry in config.items():
        symbol = entry.get("symbol")
        if symbol is not None and symbol in api_apys:
            result[coin] = (api_apys[symbol], "api")
        elif entry.get("apy") is not None:
            result[coin] = (entry["apy"], "manual")
    return result


def projected_yield(staked_qty, apy, days=365):
    """Return (period_crypto, monthly_crypto) where period_crypto is the yield
    over `days` (annual scaled by days/365) and monthly is annual/12."""
    annual = staked_qty * apy
    period = annual * days / 365
    return period, annual / 12


def rewards_summary(rewards):
    """Sum realized reward quantities per coin: {coin: total_qty}."""
    summary = {}
    for r in rewards:
        summary[r["coin"]] = summary.get(r["coin"], 0.0) + r["quantity"]
    return summary


def combined_pl(portfolio_profit, rewards_value):
    """Combined profit = portfolio unrealized profit + realized-reward value."""
    return portfolio_profit + rewards_value
