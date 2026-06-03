from dataclasses import dataclass
from datetime import datetime

VALID_ACTIONS = {"buy", "sell"}
FIELDS = ("date", "coin", "action", "quantity", "price_usd", "fee_usd")


@dataclass
class Transaction:
    date: str        # ISO YYYY-MM-DD
    coin: str
    action: str      # "buy" or "sell"
    quantity: float
    price_usd: float
    fee_usd: float


def validate_row(row):
    """Build a Transaction from a dict of string fields. Raises ValueError on
    any invalid field, naming the offending field in the message."""
    try:
        datetime.strptime(row["date"], "%Y-%m-%d")
    except (KeyError, ValueError):
        raise ValueError(f"date must be ISO YYYY-MM-DD, got {row.get('date')!r}")

    coin = (row.get("coin") or "").strip()
    if not coin:
        raise ValueError("coin must be non-empty")

    action = (row.get("action") or "").strip().lower()
    if action not in VALID_ACTIONS:
        raise ValueError(f"action must be one of {sorted(VALID_ACTIONS)}, got {action!r}")

    try:
        quantity = float(row["quantity"])
    except (KeyError, ValueError, TypeError):
        raise ValueError(f"quantity must be a number, got {row.get('quantity')!r}")
    if quantity <= 0:
        raise ValueError(f"quantity must be > 0, got {quantity}")

    try:
        price_usd = float(row["price_usd"])
    except (KeyError, ValueError, TypeError):
        raise ValueError(f"price_usd must be a number, got {row.get('price_usd')!r}")
    if price_usd < 0:
        raise ValueError(f"price_usd must be >= 0, got {price_usd}")

    try:
        fee_usd = float(row.get("fee_usd", 0) or 0)
    except (ValueError, TypeError):
        raise ValueError(f"fee_usd must be a number, got {row.get('fee_usd')!r}")
    if fee_usd < 0:
        raise ValueError(f"fee_usd must be >= 0, got {fee_usd}")

    return Transaction(row["date"], coin, action, quantity, price_usd, fee_usd)
