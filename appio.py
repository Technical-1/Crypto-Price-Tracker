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


def save_ledger(path: str, txs: list[coinbasis.Transaction]) -> None:
    """Atomically overwrite ledger.json with the coinbasis schema."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(_serde.ledger_to_json(txs, indent=2))
    os.replace(tmp, path)
