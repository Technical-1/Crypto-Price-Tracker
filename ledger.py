import csv
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime

VALID_ACTIONS = {"buy", "sell"}
FIELDS = ("date", "coin", "action", "quantity", "price_usd", "fee_usd")


@dataclass(frozen=True)
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


def load_ledger(path):
    """Return a list[Transaction] from the JSON ledger, or [] if it does not exist."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    return [Transaction(**row) for row in data]


def save_ledger(path, txns):
    """Write the transactions to the JSON ledger (overwrites)."""
    with open(path, "w") as f:
        json.dump([asdict(t) for t in txns], f, indent=2)


def import_csv(csv_path, ledger_path):
    """Append valid rows from a CSV into the JSON ledger. Returns (added, skipped).
    Invalid rows are reported on stderr and skipped; exact duplicates of rows
    already in the ledger (or earlier in this file) are skipped."""
    existing = load_ledger(ledger_path)
    seen = set(existing)  # Transaction is a frozen-comparable dataclass
    added, skipped = 0, 0
    with open(csv_path, newline="") as f:
        for lineno, row in enumerate(csv.DictReader(f), start=2):
            try:
                txn = validate_row(row)
            except ValueError as err:
                coin_hint = row.get("coin", "")
                print(f"  (skipped CSV line {lineno} [{coin_hint}]: {err})", file=sys.stderr)
                skipped += 1
                continue
            if txn in seen:
                print(f"  (skipped CSV line {lineno}: duplicate of existing entry)", file=sys.stderr)
                skipped += 1
                continue
            existing.append(txn)
            seen.add(txn)
            added += 1
    save_ledger(ledger_path, existing)
    return added, skipped
