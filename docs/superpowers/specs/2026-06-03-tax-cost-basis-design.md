# Tax & Cost-Basis Analysis — Design Spec

**Issue:** #1 — Implement Automated Tax and Cost-Basis Analysis
**Date:** 2026-06-03
**Author:** Jacob Kanfer

## Context

`Crypto-Price-Tracker` is a dependency-light Python CLI that fetches live prices
from CoinGecko and prints a per-coin profit/loss table. The only runtime
dependency is `requests`. This feature adds tax and cost-basis analysis while
keeping the tool CLI-native and dependency-light (Python stdlib only for the new
code: `csv`, `json`, `datetime`, `argparse`).

Decisions locked in during brainstorming:

- **Architecture:** keep it a CLI tool (no web frontend).
- **Sequencing:** this is the first of the 5 issues, built fully before the next.
- **Tax depth:** built-in US presets plus a configurable-rate fallback.
- **Transaction input:** all three — CSV import, interactive entry, and a
  canonical JSON ledger file.
- **Holdings:** the ledger is the single source of truth; current holdings are
  derived by replaying the ledger, with the hardcoded `originalHoldings` dict as
  a fallback/seed only.

## Goals

1. Record buy/sell transactions (with fees) via CSV import and interactive entry,
   persisted in a canonical JSON ledger.
2. Compute cost basis using FIFO (default), LIFO, or average cost.
3. Classify realized gains as short-term (≤ 365 days) or long-term (> 365 days).
4. Show unrealized gains/losses against live market prices.
5. Estimate tax liability using a US preset, configurable for other rates.

## Non-Goals

- Full per-country tax-law engines (brackets beyond the shipped US preset, wash
  sales, allowances, income tax interactions).
- A web/GUI frontend.
- Multi-currency cost basis (USD only, matching the existing tool).

## Architecture

The current single file stays a working CLI; small focused modules are added
around it so each piece is independently testable. `requests` remains the only
pip dependency.

```
CryptoPriceTracker.py   # entry point: argparse subcommands; default (no args) = price table
ledger.py               # Transaction dataclass; load/save JSON ledger; CSV import; interactive append
holdings.py             # replay ledger -> current holdings (qty + cost basis); feeds the price table
costbasis.py            # FIFO / LIFO / average lot-matching -> realized disposals w/ gain & holding period
tax.py                  # classify short/long-term; US preset + configurable rates; estimate liability
report.py               # format the tax report + realized/unrealized tables
taxconfig.json          # rates config (US preset shipped; editable for other jurisdictions)
transactions.csv        # sample/template import file
```

`fetch_prices`, `compute_profit`, and `main` keep their current signatures so the
existing test suite stays green. `main` learns to derive holdings from the ledger
when one exists, falling back to `originalHoldings`.

## Data Model

### Transaction

| Field       | Type   | Notes                                  |
|-------------|--------|----------------------------------------|
| `date`      | str    | ISO `YYYY-MM-DD`                       |
| `coin`      | str    | CoinGecko id (e.g. `bitcoin`)          |
| `action`    | str    | `buy` or `sell`                        |
| `quantity`  | float  | units of the coin, > 0                 |
| `price_usd` | float  | USD price per unit at transaction time |
| `fee_usd`   | float  | USD fee, ≥ 0                           |

Stored canonically as a list of objects in `ledger.json`.

### Input paths

- **CSV import** (`import FILE.csv`): columns
  `date,coin,action,quantity,price_usd,fee_usd`. Rows are validated; invalid rows
  are skipped with a stderr notice and the run continues. Exact duplicates of
  existing ledger entries are not re-added.
- **Interactive entry** (`add`): prompts for each field, validates, appends one
  transaction.

## Cost-Basis Engine (`costbasis.py`)

Replays the ledger chronologically. Buys create lots `(date, quantity, basis)`
where basis includes the buy fee. Each sell consumes lots per the chosen method:

- **FIFO** (default): consume oldest lots first.
- **LIFO**: consume newest lots first.
- **average**: single running average basis across all held units.

Fee handling: a buy fee increases the lot's cost basis; a sell fee reduces
proceeds. Each disposal produces: `proceeds`, `cost_basis`, `realized_gain`
(`proceeds - cost_basis`), and `holding_days` (sell date − acquired lot date).
Selling more than is held is reported as an error for that disposal and skipped
with a stderr notice.

Short-term vs long-term: `holding_days <= 365` → short-term, else long-term. The
boundary is exactly 365 days inclusive on the short-term side.

## Tax Engine (`tax.py`)

Sums realized gains into short-term and long-term buckets, optionally filtered to
a single tax year via `--year`.

`taxconfig.json` ships a US preset:

```json
{
  "jurisdiction": "US",
  "long_term_threshold_days": 365,
  "short_term_rate": 0.35,
  "long_term_brackets": [
    {"up_to": 47025,  "rate": 0.0},
    {"up_to": 518900, "rate": 0.15},
    {"up_to": null,   "rate": 0.20}
  ]
}
```

Long-term gains are taxed using the bracket table; short-term gains use the flat
`short_term_rate`. Any jurisdiction is supported by editing the rates. A
malformed or missing config falls back to documented defaults
(35% short-term, 15% flat long-term, 365-day threshold) with a stderr warning.

## CLI Surface

```
python3 CryptoPriceTracker.py                 # live price/profit table (unchanged default)
python3 CryptoPriceTracker.py import FILE.csv # import transactions from CSV
python3 CryptoPriceTracker.py add             # interactive add of one transaction
python3 CryptoPriceTracker.py tax [--method fifo|lifo|average] [--year YYYY]
                                              # realized gains (short/long), unrealized P/L
                                              # against live prices, and estimated tax
```

The no-argument invocation keeps today's behavior exactly.

## Output (`report.py`)

The `tax` report prints, as aligned text tables:

1. **Realized gains** — per disposal and totaled, split short-term / long-term.
2. **Unrealized P/L** — current holdings (from the ledger) valued at live prices
   vs cost basis.
3. **Estimated tax** — liability per bucket and total, naming the config source.

## Error Handling

Follows the existing ethos:

- Bad CSV rows are skipped with a stderr notice; the run continues.
- An empty or missing ledger gives a clear message instead of a traceback.
- Network failures during the unrealized-P/L section reuse the existing graceful
  handling (readable message, non-zero exit).
- A malformed `taxconfig.json` falls back to documented defaults with a warning.
- Overselling a coin (sell quantity exceeds held lots) is reported and skipped.

## Testing

`pytest`, mirroring the current style — no network (prices mocked). Coverage:

- CSV import: valid rows appended, invalid rows skipped, duplicates ignored.
- FIFO / LIFO / average lot matching, including partial-lot sells.
- Fee handling raises basis on buy and lowers proceeds on sell.
- Short/long-term classification at exactly 365 days.
- Tax bucket math against the US preset and a custom config.
- Empty-ledger and malformed-config fallback paths.
- Existing suite (`fetch_prices`, `compute_profit`, `main`) remains green.

## Out of Scope / Future

Later issues (#5 historical playback, #2 rebalancing, #3 staking) will reuse the
ledger and holdings-derivation modules introduced here.
