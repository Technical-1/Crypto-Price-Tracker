"""All file/config I/O for the Crypto-Price-Tracker app.

This is the app's ONLY I/O boundary.  No business logic; no cost-basis math.
All ledger-schema translation and migration lives here.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import coinbasis
import coinbasis.serde as _serde

DEFAULT_WALLET = "default"

# ── Ledger variant tag set (the 8 coinbasis event types) ──────────────────────
_COINBASIS_TAGS = frozenset({
    "Buy", "Sell", "Trade", "Income", "Spend",
    "Transfer", "GiftSent", "GiftReceived",
})
_V1_ACTIONS = frozenset({"buy", "sell"})


def _is_coinbasis_schema(rows: list) -> bool:
    """True if the array is empty OR every element is a single-key dict whose
    key is one of the 8 coinbasis variant tags."""
    if not rows:
        return True
    return all(
        isinstance(r, dict) and len(r) == 1 and next(iter(r)) in _COINBASIS_TAGS
        for r in rows
    )


def _is_v1_schema(rows: list) -> bool:
    """True if every element has the V1 flat keys and a recognised action."""
    return all(
        isinstance(r, dict)
        and "action" in r
        and r.get("action", "").lower() in _V1_ACTIONS
        and "date" in r
        and "coin" in r
        for r in rows
    )


def load_ledger(path: str, *, no_migrate: bool = False) -> list[coinbasis.Transaction]:
    """Load ledger.json.  Detects V1 flat schema and auto-migrates in-place
    (writing a .v1.bak backup first) unless `no_migrate` is True.

    Raises SystemExit(1) on missing/unreadable file or unrecognised schema.
    Per-row validation failures are skipped with a stderr notice.
    """
    if not os.path.exists(path):
        print(
            f"No ledger found at {path}. Use 'import FILE.csv' or 'add' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with open(path) as f:
            raw_text = f.read()
        rows = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read ledger {path}: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(rows, list):
        print(f"Ledger {path}: expected a JSON array.", file=sys.stderr)
        sys.exit(1)

    if _is_coinbasis_schema(rows):
        return _parse_coinbasis_rows(rows, path)

    if _is_v1_schema(rows):
        if no_migrate:
            print(
                "(ledger.json is in legacy V1 format; run 'migrate' to upgrade)",
                file=sys.stderr,
            )
            sys.exit(1)
        return _auto_migrate(path, rows)

    print(
        f"Ledger {path}: unrecognised schema (mixed or unknown format). "
        "Check the first entry.",
        file=sys.stderr,
    )
    sys.exit(1)


def _parse_coinbasis_rows(rows: list, path: str) -> list[coinbasis.Transaction]:
    """Parse a list of externally-tagged coinbasis dicts into Transaction objects.
    Per-row failures are skipped with a stderr notice."""
    txs: list[coinbasis.Transaction] = []
    raw_json = json.dumps(rows)
    try:
        txs = _serde.ledger_from_json(raw_json)
    except Exception:
        # Fallback: row-by-row for a better skip-notice
        txs = []
        for i, row in enumerate(rows):
            try:
                [tx] = _serde.ledger_from_json(json.dumps([row]))
                txs.append(tx)
            except Exception as row_exc:
                print(
                    f"(skipped ledger entry {i}: {row_exc})",
                    file=sys.stderr,
                )
    return txs


def _utc_midnight(date_str: str) -> datetime:
    """Parse 'YYYY-MM-DD' → tz-aware UTC midnight datetime."""
    y, m, d = (int(x) for x in date_str.split("-"))
    return datetime(y, m, d, tzinfo=timezone.utc)


def migrate_v1_ledger(rows: list[dict]) -> list[coinbasis.Transaction]:
    """Convert a V1 flat ledger array to a list of coinbasis Transactions.

    Maps each V1 row:
        action == "buy"  → coinbasis.Buy(wallet=DEFAULT_WALLET, ...)
        action == "sell" → coinbasis.Sell(wallet=DEFAULT_WALLET, ...)

    Numbers go through Decimal(str(x)) for lossless conversion.
    Invalid rows (validate() failure) are skipped with a stderr notice.
    """
    txs: list[coinbasis.Transaction] = []
    for i, row in enumerate(rows):
        try:
            ts = _utc_midnight(row["date"])
            asset = str(row["coin"])
            qty = Decimal(str(row["quantity"]))
            price = Decimal(str(row["price_usd"]))
            fee = Decimal(str(row["fee_usd"]))
            action = str(row.get("action", "")).lower()

            if action == "buy":
                tx: coinbasis.Transaction = coinbasis.Buy(
                    timestamp=ts, wallet=DEFAULT_WALLET, asset=asset,
                    quantity=qty, unit_price=price, fee=fee,
                )
            elif action == "sell":
                tx = coinbasis.Sell(
                    timestamp=ts, wallet=DEFAULT_WALLET, asset=asset,
                    quantity=qty, unit_price=price, fee=fee,
                )
            else:
                print(
                    f"(skipped ledger entry {i}: unknown action '{action}')",
                    file=sys.stderr,
                )
                continue

            tx.validate()
            txs.append(tx)
        except (coinbasis.PortfolioError, KeyError, ValueError, TypeError) as exc:
            print(f"(skipped ledger entry {i}: {exc})", file=sys.stderr)
    return txs


def _auto_migrate(path: str, v1_rows: list[dict]) -> list[coinbasis.Transaction]:
    """Upgrade a V1 ledger in-place:
    1. Write .v1.bak (only if absent).
    2. Convert rows with migrate_v1_ledger.
    3. Rewrite ledger.json in coinbasis schema.
    4. Print a migration notice to stderr.
    """
    bak_path = path + ".v1.bak"
    if not os.path.exists(bak_path):
        with open(bak_path, "w") as f:
            json.dump(v1_rows, f, indent=2)

    txs = migrate_v1_ledger(v1_rows)
    save_ledger(path, txs)

    print(
        f"(migrated {os.path.basename(path)} from the legacy format to the "
        f"multi-wallet schema; backup at {os.path.basename(bak_path)})",
        file=sys.stderr,
    )
    return txs


def migrate_command(ledger_path: str, *, dry_run: bool = False) -> None:
    """Explicit migrate subcommand.

    dry_run=True: describe what would happen without writing anything.
    dry_run=False: upgrade in-place (same as auto-migration on load).
    """
    if not os.path.exists(ledger_path):
        print(f"No ledger found at {ledger_path}.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(ledger_path) as f:
            rows = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read ledger: {exc}", file=sys.stderr)
        sys.exit(1)

    if _is_coinbasis_schema(rows):
        print("Ledger is already in the coinbasis multi-wallet schema. No migration needed.")
        return

    if not _is_v1_schema(rows):
        print("Ledger has an unrecognised format; cannot migrate.", file=sys.stderr)
        sys.exit(1)

    txs = migrate_v1_ledger(rows)
    n = len(txs)

    if dry_run:
        print(
            f"[dry-run] Would migrate {n} transaction(s) from V1 format to "
            f"the coinbasis multi-wallet schema.\n"
            f"  backup  → {os.path.basename(ledger_path)}.v1.bak (if not already present)\n"
            f"  rewrite → {os.path.basename(ledger_path)} (coinbasis externally-tagged JSON)"
        )
    else:
        _auto_migrate(ledger_path, rows)
        print(
            f"Migrated {n} transaction(s). Backup at "
            f"{os.path.basename(ledger_path)}.v1.bak"
        )


def save_ledger(path: str, txs: list[coinbasis.Transaction]) -> None:
    """Atomically overwrite ledger.json with the coinbasis schema."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(_serde.ledger_to_json(txs, indent=2))
    os.replace(tmp, path)
