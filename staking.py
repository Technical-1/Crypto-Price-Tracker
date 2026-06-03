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
