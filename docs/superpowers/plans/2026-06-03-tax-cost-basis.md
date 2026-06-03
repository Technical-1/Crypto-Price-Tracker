# Tax & Cost-Basis Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CLI tax & cost-basis analysis (transaction ledger, FIFO/LIFO/average cost basis, short/long-term realized gains, unrealized P/L, US-preset tax estimate) to the existing crypto price tracker.

**Architecture:** Keep the single-file CLI working and add small focused stdlib-only modules around it: `ledger.py` (transactions + persistence + import), `costbasis.py` (lot matching), `holdings.py` (ledger → current holdings), `tax.py` (config + liability), `report.py` (formatting). `CryptoPriceTracker.py` gains argparse subcommands; its existing functions keep their signatures so the current test suite stays green.

**Tech Stack:** Python 3, stdlib (`csv`, `json`, `datetime`, `argparse`, `dataclasses`), `requests` (existing), `pytest`.

---

## File Structure

- `ledger.py` — `Transaction` dataclass, validation, JSON load/save, CSV import, interactive add.
- `costbasis.py` — `Lot`, `Disposal` dataclasses, `process_ledger(txns, method, long_term_threshold)` → `(disposals, remaining_lots)`.
- `holdings.py` — `derive_holdings(txns, method)` → `{coin: {"total", "cost"}}` from remaining lots; `load_holdings_or_default(path)`.
- `tax.py` — `load_tax_config`, `summarize`, `estimate_long_term_tax`, `estimate_tax`, `DEFAULT_CONFIG`.
- `report.py` — `format_realized`, `format_unrealized`, `format_tax` (return strings; CLI prints them).
- `CryptoPriceTracker.py` — argparse subcommands; `main` derives holdings from ledger when present.
- `taxconfig.json` — US preset (shipped).
- `transactions.csv` — sample import template.
- `tests/test_ledger.py`, `tests/test_costbasis.py`, `tests/test_holdings.py`, `tests/test_tax.py`, `tests/test_report.py`, `tests/test_cli.py` — new test modules.

Shared key names (use exactly these everywhere): holding dict = `{"total": qty, "cost": total_basis}`. `Disposal.term` ∈ `{"short", "long"}`. Config keys: `long_term_threshold_days`, `short_term_rate`, `long_term_brackets` (list of `{"up_to": float|None, "rate": float}`).

---

## Task 1: Transaction dataclass + validation

**Files:**
- Create: `ledger.py`
- Test: `tests/test_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger.py
import pytest
import ledger


def test_validate_row_builds_transaction():
    txn = ledger.validate_row({
        "date": "2024-01-15", "coin": "bitcoin", "action": "buy",
        "quantity": "0.5", "price_usd": "40000", "fee_usd": "10",
    })
    assert txn == ledger.Transaction("2024-01-15", "bitcoin", "buy", 0.5, 40000.0, 10.0)


def test_validate_row_rejects_bad_action():
    with pytest.raises(ValueError, match="action"):
        ledger.validate_row({
            "date": "2024-01-15", "coin": "bitcoin", "action": "trade",
            "quantity": "1", "price_usd": "1", "fee_usd": "0",
        })


def test_validate_row_rejects_nonpositive_quantity():
    with pytest.raises(ValueError, match="quantity"):
        ledger.validate_row({
            "date": "2024-01-15", "coin": "bitcoin", "action": "buy",
            "quantity": "0", "price_usd": "1", "fee_usd": "0",
        })


def test_validate_row_rejects_bad_date():
    with pytest.raises(ValueError, match="date"):
        ledger.validate_row({
            "date": "15-01-2024", "coin": "bitcoin", "action": "buy",
            "quantity": "1", "price_usd": "1", "fee_usd": "0",
        })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ledger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ledger'`

- [ ] **Step 3: Write minimal implementation**

```python
# ledger.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ledger.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add ledger.py tests/test_ledger.py
git commit -m "feat: add Transaction model and row validation"
```

---

## Task 2: JSON ledger load/save

**Files:**
- Modify: `ledger.py`
- Test: `tests/test_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_ledger.py

def test_save_then_load_roundtrips(tmp_path):
    path = tmp_path / "ledger.json"
    txns = [
        ledger.Transaction("2024-01-15", "bitcoin", "buy", 0.5, 40000.0, 10.0),
        ledger.Transaction("2024-06-01", "bitcoin", "sell", 0.2, 60000.0, 5.0),
    ]
    ledger.save_ledger(str(path), txns)
    loaded = ledger.load_ledger(str(path))
    assert loaded == txns


def test_load_missing_file_returns_empty(tmp_path):
    assert ledger.load_ledger(str(tmp_path / "nope.json")) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ledger.py -k roundtrip -v`
Expected: FAIL with `AttributeError: module 'ledger' has no attribute 'save_ledger'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to ledger.py
import json
from dataclasses import asdict


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ledger.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add ledger.py tests/test_ledger.py
git commit -m "feat: add JSON ledger load/save"
```

---

## Task 3: CSV import

**Files:**
- Modify: `ledger.py`
- Test: `tests/test_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_ledger.py

def test_import_csv_appends_valid_skips_invalid_and_dupes(tmp_path, capsys):
    csv_path = tmp_path / "txns.csv"
    csv_path.write_text(
        "date,coin,action,quantity,price_usd,fee_usd\n"
        "2024-01-15,bitcoin,buy,0.5,40000,10\n"        # valid
        "2024-02-01,ethereum,trade,1,2000,1\n"          # invalid action -> skipped
        "2024-01-15,bitcoin,buy,0.5,40000,10\n"         # exact dupe of row 1 -> one kept
    )
    ledger_path = tmp_path / "ledger.json"
    added, skipped = ledger.import_csv(str(csv_path), str(ledger_path))
    assert added == 1
    assert skipped == 2
    loaded = ledger.load_ledger(str(ledger_path))
    assert loaded == [ledger.Transaction("2024-01-15", "bitcoin", "buy", 0.5, 40000.0, 10.0)]
    assert "ethereum" in capsys.readouterr().err  # skip notice on stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ledger.py -k import_csv -v`
Expected: FAIL with `AttributeError: module 'ledger' has no attribute 'import_csv'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to ledger.py
import csv
import sys


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
                print(f"  (skipped CSV line {lineno}: {err})", file=sys.stderr)
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
```

Note: `seen = set(...)` requires `Transaction` to be hashable. Make the dataclass hashable by changing its decorator in `ledger.py` to `@dataclass(frozen=True)`.

- [ ] **Step 4: Update the dataclass decorator**

In `ledger.py`, change `@dataclass` above `class Transaction` to `@dataclass(frozen=True)`.

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ledger.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add ledger.py tests/test_ledger.py
git commit -m "feat: add CSV import with validation and dedupe"
```

---

## Task 4: Interactive add

**Files:**
- Modify: `ledger.py`
- Test: `tests/test_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_ledger.py

def test_add_interactive_appends_one(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    answers = iter(["2024-03-01", "ethereum", "buy", "2", "1500", "3"])
    txn = ledger.add_interactive(str(ledger_path), input_fn=lambda _prompt: next(answers))
    assert txn == ledger.Transaction("2024-03-01", "ethereum", "buy", 2.0, 1500.0, 3.0)
    assert ledger.load_ledger(str(ledger_path)) == [txn]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ledger.py -k add_interactive -v`
Expected: FAIL with `AttributeError: module 'ledger' has no attribute 'add_interactive'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to ledger.py

def add_interactive(ledger_path, input_fn=input):
    """Prompt for one transaction's fields, validate, append it, and return it.
    input_fn is injectable for testing."""
    row = {
        "date": input_fn("date (YYYY-MM-DD): "),
        "coin": input_fn("coin id (e.g. bitcoin): "),
        "action": input_fn("action (buy/sell): "),
        "quantity": input_fn("quantity: "),
        "price_usd": input_fn("price per unit (USD): "),
        "fee_usd": input_fn("fee (USD): "),
    }
    txn = validate_row(row)
    txns = load_ledger(ledger_path)
    txns.append(txn)
    save_ledger(ledger_path, txns)
    return txn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ledger.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add ledger.py tests/test_ledger.py
git commit -m "feat: add interactive transaction entry"
```

---

## Task 5: Cost-basis engine — FIFO

**Files:**
- Create: `costbasis.py`
- Test: `tests/test_costbasis.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_costbasis.py
import costbasis
from ledger import Transaction


def test_fifo_single_buy_then_full_sell():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-02-01", "bitcoin", "sell", 1.0, 150.0, 0.0),
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert len(disposals) == 1
    d = disposals[0]
    assert d.coin == "bitcoin"
    assert d.quantity == 1.0
    assert d.proceeds == 150.0
    assert d.cost_basis == 100.0
    assert d.realized_gain == 50.0
    assert d.term == "short"
    assert remaining.get("bitcoin", []) == []


def test_fifo_consumes_oldest_lot_first_across_two_lots():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-03-01", "bitcoin", "buy", 1.0, 200.0, 0.0),
        Transaction("2024-04-01", "bitcoin", "sell", 1.0, 300.0, 0.0),
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert len(disposals) == 1
    assert disposals[0].cost_basis == 100.0     # oldest lot consumed
    assert disposals[0].realized_gain == 200.0
    assert len(remaining["bitcoin"]) == 1
    assert remaining["bitcoin"][0].quantity == 1.0
    assert remaining["bitcoin"][0].basis_per_unit == 200.0


def test_fifo_partial_lot_sell_splits_remaining():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 2.0, 100.0, 0.0),   # basis 50/unit
        Transaction("2024-02-01", "bitcoin", "sell", 0.5, 80.0, 0.0),
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert disposals[0].quantity == 0.5
    assert disposals[0].cost_basis == 25.0       # 0.5 * 50
    assert disposals[0].proceeds == 40.0         # 0.5 * 80
    assert remaining["bitcoin"][0].quantity == 1.5


def test_buy_fee_raises_basis_sell_fee_lowers_proceeds():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 10.0),  # basis 110
        Transaction("2024-02-01", "bitcoin", "sell", 1.0, 200.0, 20.0), # proceeds 180
    ]
    disposals, _ = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert disposals[0].cost_basis == 110.0
    assert disposals[0].proceeds == 180.0
    assert disposals[0].realized_gain == 70.0


def test_long_term_boundary_at_366_days():
    txns = [
        Transaction("2023-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-01-01", "bitcoin", "sell", 0.5, 150.0, 0.0),  # 365 days -> short
        Transaction("2024-01-02", "bitcoin", "sell", 0.5, 150.0, 0.0),  # 366 days -> long
    ]
    disposals, _ = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert disposals[0].holding_days == 365
    assert disposals[0].term == "short"
    assert disposals[1].holding_days == 366
    assert disposals[1].term == "long"


def test_oversell_is_skipped_with_notice(capsys):
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-02-01", "bitcoin", "sell", 2.0, 150.0, 0.0),  # only 1.0 held
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    # the 1.0 actually held is disposed; the excess 1.0 is reported and dropped
    assert sum(d.quantity for d in disposals) == 1.0
    assert "bitcoin" in capsys.readouterr().err
    assert remaining.get("bitcoin", []) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_costbasis.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'costbasis'`

- [ ] **Step 3: Write minimal implementation**

```python
# costbasis.py
import sys
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Lot:
    date: str            # acquisition date, ISO
    quantity: float
    basis_per_unit: float  # includes allocated buy fee


@dataclass
class Disposal:
    coin: str
    sell_date: str
    quantity: float
    proceeds: float
    cost_basis: float
    realized_gain: float
    holding_days: int
    term: str            # "short" or "long"


def _days(acquired, sold):
    a = datetime.strptime(acquired, "%Y-%m-%d")
    s = datetime.strptime(sold, "%Y-%m-%d")
    return (s - a).days


def process_ledger(txns, method="fifo", long_term_threshold=365):
    """Replay transactions chronologically, producing realized Disposals and the
    Lots still held per coin. method ∈ {fifo, lifo, average}."""
    lots = {}      # coin -> list[Lot]
    disposals = []
    ordered = sorted(txns, key=lambda t: t.date)

    for t in ordered:
        bucket = lots.setdefault(t.coin, [])
        if t.action == "buy":
            basis_per_unit = (t.price_usd * t.quantity + t.fee_usd) / t.quantity
            bucket.append(Lot(t.date, t.quantity, basis_per_unit))
            continue

        # sell
        remaining_to_sell = t.quantity
        held = sum(l.quantity for l in bucket)
        if t.quantity > held + 1e-12:
            print(f"  (warning {t.coin} {t.date}: sell of {t.quantity} exceeds "
                  f"held {held}; selling only {held})", file=sys.stderr)
            remaining_to_sell = held

        while remaining_to_sell > 1e-12 and bucket:
            lot = bucket[0] if method != "lifo" else bucket[-1]
            take = min(lot.quantity, remaining_to_sell)
            fee_share = t.fee_usd * (take / t.quantity)
            proceeds = take * t.price_usd - fee_share
            basis_per_unit = _basis_for(method, lot, bucket)
            cost_basis = take * basis_per_unit
            holding_days = _days(lot.date, t.date)
            disposals.append(Disposal(
                coin=t.coin, sell_date=t.date, quantity=take,
                proceeds=proceeds, cost_basis=cost_basis,
                realized_gain=proceeds - cost_basis,
                holding_days=holding_days,
                term="short" if holding_days <= long_term_threshold else "long",
            ))
            lot.quantity -= take
            remaining_to_sell -= take
            if lot.quantity <= 1e-12:
                bucket.remove(lot)

    return disposals, {c: ls for c, ls in lots.items()}


def _basis_for(method, lot, bucket):
    if method == "average":
        total_qty = sum(l.quantity for l in bucket)
        total_basis = sum(l.quantity * l.basis_per_unit for l in bucket)
        return total_basis / total_qty if total_qty else lot.basis_per_unit
    return lot.basis_per_unit
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_costbasis.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add costbasis.py tests/test_costbasis.py
git commit -m "feat: add FIFO cost-basis engine with lot matching"
```

---

## Task 6: LIFO method

**Files:**
- Test: `tests/test_costbasis.py` (LIFO already wired in Task 5; add coverage)

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_costbasis.py

def test_lifo_consumes_newest_lot_first():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-03-01", "bitcoin", "buy", 1.0, 200.0, 0.0),
        Transaction("2024-04-01", "bitcoin", "sell", 1.0, 300.0, 0.0),
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="lifo", long_term_threshold=365)
    assert disposals[0].cost_basis == 200.0     # newest lot consumed
    assert disposals[0].realized_gain == 100.0
    assert remaining["bitcoin"][0].basis_per_unit == 100.0  # oldest lot remains
```

- [ ] **Step 2: Run test to verify it passes (LIFO branch exists from Task 5)**

Run: `python3 -m pytest tests/test_costbasis.py -k lifo -v`
Expected: PASS

If it fails, confirm the `lot = bucket[-1] if method == "lifo"` selection in `process_ledger`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_costbasis.py
git commit -m "test: cover LIFO lot matching"
```

---

## Task 7: Average-cost method

**Files:**
- Test: `tests/test_costbasis.py` (average branch wired in Task 5; add coverage)

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_costbasis.py

def test_average_uses_pooled_basis():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-03-01", "bitcoin", "buy", 3.0, 300.0, 0.0),  # 300 for 3 -> 100/unit
        Transaction("2024-04-01", "bitcoin", "sell", 2.0, 250.0, 0.0),
    ]
    # pooled basis = (100 + 900)/4 = 250 total / ... per-unit = (100*1 + 100*3)/4 = 100
    disposals, _ = costbasis.process_ledger(txns, method="average", long_term_threshold=365)
    assert sum(d.cost_basis for d in disposals) == 200.0   # 2 units * 100 avg
    assert sum(d.proceeds for d in disposals) == 500.0     # 2 * 250
    assert sum(d.realized_gain for d in disposals) == 300.0
```

- [ ] **Step 2: Run test to verify it passes (average branch exists from Task 5)**

Run: `python3 -m pytest tests/test_costbasis.py -k average -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_costbasis.py
git commit -m "test: cover average-cost lot matching"
```

---

## Task 8: Holdings derivation

**Files:**
- Create: `holdings.py`
- Test: `tests/test_holdings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_holdings.py
import holdings
from ledger import Transaction


def test_derive_holdings_from_remaining_lots():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 2.0, 100.0, 0.0),   # 200 basis
        Transaction("2024-02-01", "bitcoin", "sell", 1.0, 150.0, 0.0),  # 1 left, 100 basis
        Transaction("2024-01-01", "ethereum", "buy", 5.0, 10.0, 0.0),   # 50 basis
    ]
    result = holdings.derive_holdings(txns, method="fifo")
    assert result["bitcoin"] == {"total": 1.0, "cost": 100.0}
    assert result["ethereum"] == {"total": 5.0, "cost": 50.0}


def test_derive_holdings_omits_fully_sold_coin():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-02-01", "bitcoin", "sell", 1.0, 150.0, 0.0),
    ]
    assert "bitcoin" not in holdings.derive_holdings(txns, method="fifo")


def test_load_holdings_or_default_falls_back(tmp_path):
    fallback = {"bitcoin": {"total": 1, "cost": 200}}
    result = holdings.load_holdings_or_default(
        str(tmp_path / "missing.json"), fallback=fallback)
    assert result == fallback


def test_load_holdings_or_default_uses_ledger_when_present(tmp_path):
    import ledger
    path = tmp_path / "ledger.json"
    ledger.save_ledger(str(path), [Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0)])
    result = holdings.load_holdings_or_default(str(path), fallback={"x": {"total": 1, "cost": 1}})
    assert result == {"bitcoin": {"total": 1.0, "cost": 100.0}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_holdings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'holdings'`

- [ ] **Step 3: Write minimal implementation**

```python
# holdings.py
import costbasis
import ledger


def derive_holdings(txns, method="fifo"):
    """Return {coin: {"total": qty, "cost": total_basis}} for coins still held,
    from the lots remaining after replaying the ledger."""
    _, remaining = costbasis.process_ledger(txns, method=method)
    result = {}
    for coin, lots in remaining.items():
        total = sum(l.quantity for l in lots)
        if total <= 1e-12:
            continue
        cost = sum(l.quantity * l.basis_per_unit for l in lots)
        result[coin] = {"total": total, "cost": cost}
    return result


def load_holdings_or_default(ledger_path, fallback, method="fifo"):
    """Derive holdings from the ledger if it has any transactions; otherwise
    return the fallback dict (the hardcoded originalHoldings)."""
    txns = ledger.load_ledger(ledger_path)
    if not txns:
        return fallback
    return derive_holdings(txns, method=method)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_holdings.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add holdings.py tests/test_holdings.py
git commit -m "feat: derive current holdings from the ledger"
```

---

## Task 9: Tax config loading

**Files:**
- Create: `tax.py`
- Create: `taxconfig.json`
- Test: `tests/test_tax.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tax.py
import json
import tax


def test_load_config_reads_valid_file(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({
        "jurisdiction": "US", "long_term_threshold_days": 365,
        "short_term_rate": 0.35,
        "long_term_brackets": [{"up_to": None, "rate": 0.15}],
    }))
    cfg = tax.load_tax_config(str(path))
    assert cfg["short_term_rate"] == 0.35


def test_load_config_missing_file_uses_defaults(tmp_path, capsys):
    cfg = tax.load_tax_config(str(tmp_path / "nope.json"))
    assert cfg == tax.DEFAULT_CONFIG
    assert "default tax config" in capsys.readouterr().err


def test_load_config_malformed_uses_defaults(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{ not json")
    cfg = tax.load_tax_config(str(path))
    assert cfg == tax.DEFAULT_CONFIG
    assert "default tax config" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_tax.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tax'`

- [ ] **Step 3: Write minimal implementation**

```python
# tax.py
import json
import sys

DEFAULT_CONFIG = {
    "jurisdiction": "default",
    "long_term_threshold_days": 365,
    "short_term_rate": 0.35,
    "long_term_brackets": [{"up_to": None, "rate": 0.15}],
}

REQUIRED_KEYS = ("long_term_threshold_days", "short_term_rate", "long_term_brackets")


def load_tax_config(path):
    """Load the tax config JSON, falling back to DEFAULT_CONFIG (with a stderr
    warning) if the file is missing, unreadable, or missing required keys."""
    try:
        with open(path) as f:
            cfg = json.load(f)
        for key in REQUIRED_KEYS:
            if key not in cfg:
                raise KeyError(key)
        return cfg
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as err:
        print(f"Warning: using default tax config ({err})", file=sys.stderr)
        return dict(DEFAULT_CONFIG)
```

```json
// taxconfig.json
{
  "jurisdiction": "US",
  "long_term_threshold_days": 365,
  "short_term_rate": 0.35,
  "long_term_brackets": [
    {"up_to": 47025, "rate": 0.0},
    {"up_to": 518900, "rate": 0.15},
    {"up_to": null, "rate": 0.20}
  ]
}
```

Note: JSON does not allow `//` comments — create `taxconfig.json` without the comment line.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_tax.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add tax.py taxconfig.json tests/test_tax.py
git commit -m "feat: add tax config loading with US preset and defaults"
```

---

## Task 10: Tax summary + liability

**Files:**
- Modify: `tax.py`
- Test: `tests/test_tax.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_tax.py
from costbasis import Disposal


def _d(term, gain, sell_date="2024-05-01"):
    return Disposal("bitcoin", sell_date, 1.0, 0.0, 0.0, gain, 10, term)


def test_summarize_splits_short_and_long():
    disposals = [_d("short", 100.0), _d("long", 200.0), _d("short", -50.0)]
    short, long = tax.summarize(disposals)
    assert short == 50.0
    assert long == 200.0


def test_summarize_filters_by_year():
    disposals = [_d("short", 100.0, "2023-05-01"), _d("short", 40.0, "2024-05-01")]
    short, long = tax.summarize(disposals, year=2024)
    assert short == 40.0
    assert long == 0.0


def test_estimate_long_term_tax_progressive_brackets():
    brackets = [{"up_to": 100.0, "rate": 0.0}, {"up_to": 200.0, "rate": 0.15},
                {"up_to": None, "rate": 0.20}]
    # 250 gain: 0 on first 100, 15% on next 100 (15), 20% on last 50 (10) = 25
    assert tax.estimate_long_term_tax(250.0, brackets) == 25.0


def test_estimate_tax_floors_losses_at_zero():
    cfg = {"short_term_rate": 0.35,
           "long_term_brackets": [{"up_to": None, "rate": 0.15}]}
    st, lt = tax.estimate_tax(-100.0, -50.0, cfg)
    assert st == 0.0
    assert lt == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_tax.py -k "summarize or estimate" -v`
Expected: FAIL with `AttributeError: module 'tax' has no attribute 'summarize'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to tax.py

def summarize(disposals, year=None):
    """Return (short_gain, long_gain) summed across disposals, optionally
    filtered to those whose sell_date falls in the given calendar year."""
    selected = disposals
    if year is not None:
        selected = [d for d in disposals if d.sell_date[:4] == str(year)]
    short = sum(d.realized_gain for d in selected if d.term == "short")
    long = sum(d.realized_gain for d in selected if d.term == "long")
    return short, long


def estimate_long_term_tax(gain, brackets):
    """Apply progressive bracket rates to a non-negative long-term gain."""
    if gain <= 0:
        return 0.0
    tax_due = 0.0
    lower = 0.0
    for b in brackets:
        upper = b["up_to"] if b["up_to"] is not None else float("inf")
        if gain <= lower:
            break
        taxable = min(gain, upper) - lower
        tax_due += taxable * b["rate"]
        lower = upper
    return tax_due


def estimate_tax(short_gain, long_gain, config):
    """Return (short_term_tax, long_term_tax). Net losses produce zero tax."""
    st = max(0.0, short_gain) * config["short_term_rate"]
    lt = estimate_long_term_tax(max(0.0, long_gain), config["long_term_brackets"])
    return st, lt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_tax.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add tax.py tests/test_tax.py
git commit -m "feat: add realized-gain summary and tax liability estimate"
```

---

## Task 11: Report formatting

**Files:**
- Create: `report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
import report
from costbasis import Disposal


def test_format_realized_shows_totals_and_terms():
    disposals = [
        Disposal("bitcoin", "2024-05-01", 1.0, 150.0, 100.0, 50.0, 120, "short"),
        Disposal("ethereum", "2024-06-01", 2.0, 400.0, 300.0, 100.0, 400, "long"),
    ]
    out = report.format_realized(disposals)
    assert "bitcoin" in out and "ethereum" in out
    assert "Short-term total" in out
    assert "50.00" in out and "100.00" in out


def test_format_unrealized_uses_live_prices():
    held = {"bitcoin": {"total": 1.0, "cost": 100.0}}
    prices = {"bitcoin": {"usd": 150.0}}
    out = report.format_unrealized(held, prices)
    assert "bitcoin" in out
    assert "50.00" in out  # 150 value - 100 basis


def test_format_tax_names_jurisdiction():
    cfg = {"jurisdiction": "US", "short_term_rate": 0.35,
           "long_term_brackets": [{"up_to": None, "rate": 0.15}]}
    out = report.format_tax(100.0, 200.0, 35.0, 30.0, cfg)
    assert "US" in out
    assert "35.00" in out and "30.00" in out
    assert "65.00" in out  # total
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'report'`

- [ ] **Step 3: Write minimal implementation**

```python
# report.py


def format_realized(disposals):
    """Render realized disposals as a text table with short/long-term totals."""
    lines = ["Realized gains/losses:",
             "      Coin        Sell Date    Qty      Proceeds    Basis     Gain     Term",
             "  ------------   ----------   ------   ----------   ------   ------   ------"]
    short_total = long_total = 0.0
    for d in disposals:
        if d.term == "short":
            short_total += d.realized_gain
        else:
            long_total += d.realized_gain
        lines.append("  %-12s   %-10s   %6.3f   %10.2f   %6.2f   %6.2f   %-5s" % (
            d.coin, d.sell_date, d.quantity, d.proceeds, d.cost_basis,
            d.realized_gain, d.term))
    lines.append("  Short-term total: %.2f" % short_total)
    lines.append("  Long-term total:  %.2f" % long_total)
    return "\n".join(lines)


def format_unrealized(held, prices):
    """Render current holdings valued at live prices vs cost basis."""
    lines = ["Unrealized P/L (live prices):",
             "      Coin         Qty       Value      Basis     Unrealized",
             "  ------------   ------   ----------   ------   ------------"]
    for coin, h in held.items():
        coin_price = prices.get(coin)
        if not coin_price or coin_price.get("usd") is None:
            lines.append("  (skipped %s: no price data)" % coin)
            continue
        value = h["total"] * coin_price["usd"]
        unrealized = value - h["cost"]
        lines.append("  %-12s   %6.3f   %10.2f   %6.2f   %10.2f" % (
            coin, h["total"], value, h["cost"], unrealized))
    return "\n".join(lines)


def format_tax(short_gain, long_gain, short_tax, long_tax, config):
    """Render the estimated tax summary."""
    return "\n".join([
        "Estimated tax (%s):" % config.get("jurisdiction", "default"),
        "  Short-term gain: %10.2f   tax: %8.2f" % (short_gain, short_tax),
        "  Long-term gain:  %10.2f   tax: %8.2f" % (long_gain, long_tax),
        "  Total estimated tax: %.2f" % (short_tax + long_tax),
    ])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add report.py tests/test_report.py
git commit -m "feat: add report formatting for realized, unrealized, and tax"
```

---

## Task 12: CLI subcommands + ledger-derived holdings

**Files:**
- Modify: `CryptoPriceTracker.py`
- Test: `tests/test_cli.py`, `tests/test_crypto_price_tracker.py` (existing — must stay green)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from unittest.mock import patch
import CryptoPriceTracker as cpt


def test_run_tax_command_prints_all_three_sections(tmp_path, capsys):
    import ledger
    ledger_path = tmp_path / "ledger.json"
    ledger.save_ledger(str(ledger_path), [
        ledger.Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        ledger.Transaction("2024-03-01", "bitcoin", "sell", 0.5, 200.0, 0.0),
    ])
    prices = {"bitcoin": {"usd": 300.0}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices):
        cpt.run_tax(ledger_path=str(ledger_path), taxconfig_path="taxconfig.json",
                    method="fifo", year=None)
    out = capsys.readouterr().out
    assert "Realized gains" in out
    assert "Unrealized P/L" in out
    assert "Estimated tax" in out


def test_parser_defaults_to_no_command():
    parser = cpt.build_parser()
    args = parser.parse_args([])
    assert args.command is None


def test_parser_tax_method_and_year():
    parser = cpt.build_parser()
    args = parser.parse_args(["tax", "--method", "lifo", "--year", "2024"])
    assert args.command == "tax"
    assert args.method == "lifo"
    assert args.year == 2024
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: FAIL with `AttributeError: module 'CryptoPriceTracker' has no attribute 'run_tax'`

- [ ] **Step 3: Write minimal implementation**

Add imports and new functions to `CryptoPriceTracker.py`, and replace the `__main__` block. Keep `fetch_prices`, `compute_profit`, `main`, `originalHoldings`, and `API_URL` exactly as they are, with one change inside `main` (Step 4).

```python
# add near the top of CryptoPriceTracker.py, after existing imports
import argparse

import ledger as ledger_mod
import holdings as holdings_mod
import costbasis
import tax as tax_mod
import report

LEDGER_PATH = "ledger.json"
TAXCONFIG_PATH = "taxconfig.json"
```

```python
# add these functions above the __main__ block

def run_tax(ledger_path=LEDGER_PATH, taxconfig_path=TAXCONFIG_PATH,
            method="fifo", year=None):
    """Print realized gains, unrealized P/L (live prices), and estimated tax."""
    txns = ledger_mod.load_ledger(ledger_path)
    if not txns:
        print("No transactions found. Use 'import FILE.csv' or 'add' first.",
              file=sys.stderr)
        sys.exit(1)

    config = tax_mod.load_tax_config(taxconfig_path)
    disposals, _ = costbasis.process_ledger(
        txns, method=method, long_term_threshold=config["long_term_threshold_days"])

    print(report.format_realized(disposals))
    print()

    held = holdings_mod.derive_holdings(txns, method=method)
    try:
        prices = fetch_prices(API_URL)
        print(report.format_unrealized(held, prices))
    except requests.RequestException as err:
        print(f"(unrealized P/L unavailable: {err})", file=sys.stderr)
    print()

    short_gain, long_gain = tax_mod.summarize(disposals, year=year)
    short_tax, long_tax = tax_mod.estimate_tax(short_gain, long_gain, config)
    print(report.format_tax(short_gain, long_gain, short_tax, long_tax, config))


def build_parser():
    parser = argparse.ArgumentParser(description="Crypto price tracker & tax tool")
    sub = parser.add_subparsers(dest="command")

    imp = sub.add_parser("import", help="import transactions from a CSV file")
    imp.add_argument("csv_file")

    sub.add_parser("add", help="interactively add one transaction")

    tax_cmd = sub.add_parser("tax", help="show realized gains, unrealized P/L, and estimated tax")
    tax_cmd.add_argument("--method", choices=["fifo", "lifo", "average"], default="fifo")
    tax_cmd.add_argument("--year", type=int, default=None)

    return parser


def cli(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "import":
        added, skipped = ledger_mod.import_csv(args.csv_file, LEDGER_PATH)
        print(f"Imported {added} transaction(s), skipped {skipped}.")
    elif args.command == "add":
        txn = ledger_mod.add_interactive(LEDGER_PATH)
        print(f"Added: {txn}")
    elif args.command == "tax":
        run_tax(method=args.method, year=args.year)
    else:
        main()
```

```python
# replace the existing __main__ block at the bottom
if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Make `main` derive holdings from the ledger**

In `CryptoPriceTracker.py`, change the start of `main`:

```python
def main(holdings=None, url=API_URL):
    if holdings is None:
        holdings = holdings_mod.load_holdings_or_default(LEDGER_PATH, originalHoldings)
```

This preserves existing tests (they pass `holdings=` explicitly) while making the default invocation prefer the ledger when one exists.

- [ ] **Step 5: Run tests to verify they pass (new + existing)**

Run: `python3 -m pytest tests/test_cli.py tests/test_crypto_price_tracker.py -v`
Expected: PASS (all — new CLI tests and the full existing suite)

- [ ] **Step 6: Commit**

```bash
git add CryptoPriceTracker.py tests/test_cli.py
git commit -m "feat: add import/add/tax CLI subcommands and ledger-derived holdings"
```

---

## Task 13: Sample CSV, full suite, lint, and docs

**Files:**
- Create: `transactions.csv`
- Modify: `README.md`
- Modify: `.gitignore` (ignore the user's generated `ledger.json`)

- [ ] **Step 1: Create the sample import template**

```csv
date,coin,action,quantity,price_usd,fee_usd
2024-01-15,bitcoin,buy,0.5,40000,10
2024-02-10,ethereum,buy,3,2500,5
2024-06-01,bitcoin,sell,0.2,60000,8
```

- [ ] **Step 2: Ignore the user's runtime ledger**

Add to `.gitignore`:

```
ledger.json
```

- [ ] **Step 3: Run the full test suite and lint**

Run: `python3 -m pytest -v`
Expected: PASS (all tests across every module)

Run: `python3 -m pyflakes CryptoPriceTracker.py ledger.py costbasis.py holdings.py tax.py report.py`
Expected: no output (clean)

- [ ] **Step 4: Update the README**

Add a "Tax & Cost-Basis" section documenting the subcommands, the CSV schema, the three cost-basis methods, `--year`, and that `taxconfig.json` holds editable rates (US preset shipped). Update the Project Structure tree to list the new modules. Keep the existing usage section accurate (no-arg run still prints the live table; it now prefers `ledger.json` when present).

- [ ] **Step 5: Commit**

```bash
git add transactions.csv .gitignore README.md
git commit -m "docs: document tax features; add sample CSV and ignore runtime ledger"
```

---

## Verification Checklist (run before opening the PR)

- [ ] `python3 -m pytest -v` — all green (existing + new).
- [ ] `python3 -m pyflakes *.py` — clean.
- [ ] `python3 CryptoPriceTracker.py` — still prints the live price table (uses `originalHoldings` when no `ledger.json`).
- [ ] `python3 CryptoPriceTracker.py import transactions.csv` then `python3 CryptoPriceTracker.py tax --method fifo` — prints all three report sections.
- [ ] Spec requirements covered: CSV import ✔ (T3), interactive entry ✔ (T4), JSON ledger ✔ (T2), FIFO/LIFO/average ✔ (T5-7), fees in basis/proceeds ✔ (T5), short/long-term at 365d ✔ (T5), unrealized P/L vs live prices ✔ (T11/T12), US preset + configurable + defaults ✔ (T9), tax liability ✔ (T10), `--year` ✔ (T10/T12), ledger as source of truth ✔ (T8/T12).
