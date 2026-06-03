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
