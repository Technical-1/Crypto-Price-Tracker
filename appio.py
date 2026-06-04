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

import csv as _csv

import coinbasis
import coinbasis.serde as _serde
import cryptolytics as _cl

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


def load_taxconfig(path: str) -> coinbasis.TaxConfig:
    """Load taxconfig.json → coinbasis.TaxConfig.
    Missing or invalid file → TaxConfig.default() + stderr notice."""
    if not os.path.exists(path):
        return coinbasis.TaxConfig.default()
    try:
        with open(path) as f:
            d = json.load(f)
        brackets = [
            coinbasis.TaxBracket(
                up_to=Decimal(str(b["up_to"])) if b.get("up_to") is not None else None,
                rate=Decimal(str(b["rate"])),
            )
            for b in d.get("long_term_brackets", [])
        ]
        return coinbasis.TaxConfig(
            jurisdiction=d.get("jurisdiction", "US"),
            long_term_threshold_days=int(d.get("long_term_threshold_days", 365)),
            short_term_rate=Decimal(str(d.get("short_term_rate", "0.35"))),
            long_term_brackets=brackets,
        )
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"(taxconfig.json invalid: {exc}; using defaults)", file=sys.stderr)
        return coinbasis.TaxConfig.default()


def load_targets(path: str) -> Optional[dict[str, Decimal]]:
    """Load targets.json → {coin: Decimal(weight)}.  Returns None if absent."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        return {k: Decimal(str(v)) for k, v in d.items()}
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        print(f"(targets.json invalid: {exc})", file=sys.stderr)
        return None


def load_staking_config(path: str) -> Optional[dict]:
    """Load staking.json.  Returns None if absent."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"(staking.json invalid: {exc})", file=sys.stderr)
        return None


def load_rewards(path: str) -> list[dict]:
    """Load rewards.csv → list of row dicts.  Returns [] if absent."""
    if not os.path.exists(path):
        return []
    try:
        rows = []
        with open(path, newline="") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
        return rows
    except OSError as exc:
        print(f"(rewards.csv unreadable: {exc})", file=sys.stderr)
        return []


def load_news_config(path: str) -> dict:
    """Load news.json.  Returns defaults (DEFAULT_FEEDS) if absent."""
    defaults = {"feeds": list(_cl.DEFAULT_FEEDS), "cryptopanic_token": None, "keywords": {}}
    if not os.path.exists(path):
        return defaults
    try:
        with open(path) as f:
            d = json.load(f)
        return {**defaults, **d}
    except (json.JSONDecodeError, OSError) as exc:
        print(f"(news.json invalid: {exc}; using defaults)", file=sys.stderr)
        return defaults


def load_snapshots(path: str) -> list[_cl.Snapshot]:
    """Read snapshots.jsonl → list[cryptolytics.Snapshot].  Returns [] if absent."""
    if not os.path.exists(path):
        return []
    snaps: list[_cl.Snapshot] = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                snaps.append(_cl.Snapshot(
                    date=d["date"],
                    total_value=float(d["total_value"]),
                    cost=float(d["cost"]),
                    pl=float(d["pl"]),
                ))
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"(snapshots.jsonl unreadable: {exc})", file=sys.stderr)
        return []
    return snaps


def save_snapshots(path: str, snaps: list[_cl.Snapshot]) -> None:
    """Atomically rewrite snapshots.jsonl."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for s in snaps:
            f.write(json.dumps({
                "date": s.date,
                "total_value": s.total_value,
                "cost": s.cost,
                "pl": s.pl,
            }) + "\n")
    os.replace(tmp, path)


def import_csv(csv_path: str, ledger_path: str) -> None:
    """Import transactions from CSV into ledger.json.

    Accepts V1 columns (date, coin, action, quantity, price_usd, fee_usd) and
    extended columns (wallet, plus event-specific fields).
    Deduplicates exact matches against existing entries.
    Skips invalid rows with a stderr notice.
    """
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Load existing ledger (may trigger migration if V1)
    try:
        existing = load_ledger(ledger_path) if os.path.exists(ledger_path) else []
    except SystemExit:
        existing = []

    try:
        with open(csv_path, newline="") as f:
            reader = _csv.DictReader(f)
            csv_rows = list(reader)
    except OSError as exc:
        print(f"Cannot read CSV {csv_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    new_txs: list[coinbasis.Transaction] = []
    skipped = 0
    for i, row in enumerate(csv_rows, start=2):  # 1-based header + 1-based data
        try:
            tx = _csv_row_to_tx(row)
            if tx is None:
                continue
            tx.validate()
            # Dedup: skip if an identical tx is already in existing + new_txs
            if tx in existing or tx in new_txs:
                continue
            new_txs.append(tx)
        except (coinbasis.PortfolioError, KeyError, ValueError, TypeError) as exc:
            print(f"(skipped CSV line {i}: {exc})", file=sys.stderr)
            skipped += 1

    all_txs = existing + new_txs
    save_ledger(ledger_path, all_txs)

    added = len(new_txs)
    print(f"Imported {added} transaction(s){f'; skipped {skipped} invalid row(s)' if skipped else ''}.")


def _csv_row_to_tx(row: dict) -> Optional[coinbasis.Transaction]:
    """Convert one CSV row dict to a coinbasis Transaction.  Returns None if the
    action type is unrecognised but not invalid (e.g. future extended types not
    yet handled).  Raises on field errors so the caller can print a skip notice."""
    action = str(row.get("action", "")).lower().strip()
    wallet = str(row.get("wallet", DEFAULT_WALLET)) or DEFAULT_WALLET
    ts = _utc_midnight(str(row["date"]).strip())
    asset = str(row["coin"]).strip()
    qty = Decimal(str(row["quantity"]).strip())
    price = Decimal(str(row.get("price_usd", "0")).strip())
    fee = Decimal(str(row.get("fee_usd", "0")).strip())

    if action == "buy":
        return coinbasis.Buy(timestamp=ts, wallet=wallet, asset=asset,
                             quantity=qty, unit_price=price, fee=fee)
    elif action == "sell":
        return coinbasis.Sell(timestamp=ts, wallet=wallet, asset=asset,
                              quantity=qty, unit_price=price, fee=fee)
    # Extended actions: income, spend, trade, transfer, gift_sent, gift_received
    elif action == "income":
        value = Decimal(str(row.get("value", qty * price)).strip())
        source_str = str(row.get("source", "Other")).strip()
        try:
            source = coinbasis.IncomeSource(source_str)
        except ValueError:
            source = coinbasis.IncomeSource.OTHER
        return coinbasis.Income(timestamp=ts, wallet=wallet, asset=asset,
                                quantity=qty, value=value, source=source)
    else:
        # Unknown action: skip quietly (could be a comment row or future type)
        return None
