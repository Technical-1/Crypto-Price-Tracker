# Staking / Yield Tracking — Design Spec

**Issue:** #3 — Integrate Staking/Yield Tracking
**Date:** 2026-06-03
**Author:** Jacob Kanfer

## Context

`Crypto-Price-Tracker` is a dependency-light Python CLI. Issues #1 (tax &
cost-basis) and #2 (rebalancing) added a transaction ledger / holdings model
(`holdings.py`), a resilient CoinGecko fetch pattern (`fetch_prices`), and
historical/market-cap fetching (`marketdata.py`). This feature tracks staking
yield: current APY, projected income, realized rewards, a staked-vs-not
comparison, and a combined profit/loss view. It stays CLI-native and
dependency-light (`requests` + stdlib only: `csv`, `json`).

Decisions locked in during brainstorming:

- **APY source:** best-effort from a public API (DefiLlama yields, keyless) with
  a manual fallback in `staking.json`. The API can only supply APY by symbol; it
  can never know the user's staked quantity, so quantities are always manual.
- **Realized rewards:** recorded in a separate `rewards.csv` read by the staking
  module. This keeps staking isolated and does NOT modify the issue-#1
  cost-basis engine. Rewards are valued at the current price as zero-cost income.
- **P/L integration:** a combined view inside the `staking` command (portfolio
  P/L + reward value); the existing price/tax tables are unchanged.

## Goals

1. Load staked positions (coin, staked quantity, symbol, optional manual APY)
   from `staking.json`.
2. Determine an effective APY per coin (API value if available, else manual),
   and project annual and monthly yield in crypto and USD.
3. Track realized staking rewards from `rewards.csv` and value them at the
   current price.
4. Show a staked-vs-not-staked comparison (the extra income staking provides).
5. Show a combined P/L: portfolio unrealized profit plus realized-reward value.

## Non-Goals

- A guaranteed-accurate per-protocol staking-APY feed (DefiLlama is best-effort
  and includes DeFi pools, so it is an approximation).
- Auto-discovery of staked positions or auto-detection of received rewards.
- A web/GUI frontend or charts.
- Modifying the cost-basis/tax engine or the default price table.

## Architecture

New stdlib-only modules; reuses `holdings.py` and `fetch_prices`. `requests`
remains the only pip dependency.

```
staking_api.py      # fetch_apys(symbols, timeout) -> {symbol: apy}  best-effort DefiLlama
staking.py          # load_config, load_rewards, effective_apys, projected_yield,
                    #   rewards_summary, combined P/L helpers (pure, no network)
staking_report.py   # format yield / rewards / staked-vs-unstaked / combined-P&L tables (strings)
CryptoPriceTracker.py  # new `staking [--days 365]` subcommand
staking.sample.json    # committed sample config (user's staking.json is gitignored)
rewards.sample.csv     # committed sample rewards (user's rewards.csv is gitignored)
```

## Data Model

### staking.json

```json
{
  "ethereum":  {"staked_qty": 2.0, "symbol": "ETH",  "apy": 0.04},
  "stellar":   {"staked_qty": 1000.0, "symbol": "XLM"}
}
```

- `staked_qty` (float, required, > 0).
- `symbol` (str, optional) — used to match a DefiLlama pool.
- `apy` (float, optional) — manual fallback APY as a fraction (0.04 = 4%).

### rewards.csv

Columns `date,coin,quantity`. Each row is a realized staking reward already
received. Invalid rows are skipped with a stderr notice; a missing file means
no realized rewards (not an error).

## Components

### staking_api.py (best-effort, network)

- `fetch_apys(symbols, timeout=10)` → `{symbol: apy_fraction}`. GETs DefiLlama
  `https://yields.llama.fi/pools`, and for each requested symbol selects the
  pool whose `symbol` matches exactly and has the highest `tvlUsd`, returning its
  `apy` converted from percent to a fraction. Symbols with no match are omitted.
  Raises `requests.RequestException` on network/HTTP failure (caller handles).

### staking.py (pure, no network)

- `load_config(path)` → `{coin: {"staked_qty", "symbol"?, "apy"?}}`. Raises
  `ValueError` if missing, malformed, not an object, or any entry lacks a
  positive `staked_qty`.
- `load_rewards(path)` → `list[{"date","coin","quantity"}]`. Missing file → `[]`.
  Invalid rows skipped with a stderr notice.
- `effective_apys(config, api_apys)` → `{coin: (apy, source)}` where source is
  `"api"` or `"manual"`; a coin with neither is omitted. API is matched by the
  coin's configured `symbol`.
- `projected_yield(staked_qty, apy, days=365)` → `(period_crypto, monthly_crypto)`
  where `period_crypto = staked_qty*apy*days/365` (the yield over the requested
  horizon; default 365 days = one full annual yield) and `monthly_crypto =
  staked_qty*apy/12`.
- `rewards_summary(rewards)` → `{coin: total_qty}` summed across reward rows.
- `combined_pl(portfolio_profit, rewards_value)` → their sum (rewards have zero
  cost basis, so their full current value is income/profit).

### staking_report.py (return strings, no I/O)

1. `format_yield(rows)` — per coin: APY, source, staked qty, annual & monthly
   yield (crypto and USD).
2. `format_rewards(rows, total_usd)` — per coin: reward qty, current USD value; total.
3. `format_comparison(rows, total_usd)` — extra annual income from staking, per
   coin and total (staked vs not staked).
4. `format_combined_pl(portfolio_profit, rewards_value, combined)` — the three
   figures.

## CLI Surface

```
python3 CryptoPriceTracker.py staking [--days 365]
```

`--days` sets the projection horizon (default 365 = one annual yield); the yield
table shows the yield over that horizon plus a monthly figure. The command:

1. Loads `staking.json` (error+exit if missing/invalid).
2. Fetches live prices (existing `fetch_prices`).
3. Attempts `staking_api.fetch_apys` for the configured symbols; on failure,
   falls back to manual APYs (stderr notice).
4. Computes effective APYs and projected yield; prints the yield table.
5. Loads `rewards.csv`, values rewards at live prices; prints the rewards table.
6. Prints the staked-vs-not comparison.
7. Computes portfolio unrealized profit from holdings + live prices, adds reward
   value, and prints the combined P/L.

The default (no-arg) behavior and other subcommands are unchanged.

## Error Handling

- API fetch failure → stderr notice; fall back to manual APYs per coin.
- A coin with neither API nor manual APY is skipped from the yield table with a
  notice (still counted elsewhere only if it has rewards).
- Missing/malformed `staking.json` → clear error, exit 1.
- Missing `rewards.csv` → no realized rewards (not an error). Bad reward rows
  skipped with a stderr notice.
- A coin with no live price shows crypto yield but skips its USD figure with a
  notice; live-price network failure reuses the existing readable-message /
  non-zero-exit handling.

## Testing

`pytest`, no network (mock `fetch_prices` and `staking_api.fetch_apys`).
Coverage:

- `load_config`: valid; missing file; malformed JSON; entry missing/zero
  `staked_qty` → ValueError.
- `load_rewards`: valid CSV; invalid row skipped; missing file → [].
- `effective_apys`: API present (source "api"); API missing but manual present
  (source "manual"); neither → omitted.
- `projected_yield`: known math (e.g. 2.0 @ 0.04 → 0.08 annual, 0.08/12 monthly).
- `rewards_summary`: sums multiple rows per coin.
- `combined_pl`: sum.
- `staking_api.fetch_apys`: parses DefiLlama, exact symbol match picks
  highest-TVL pool, percent→fraction; no-match symbol omitted; HTTP error propagates.
- Graceful API-failure fallback to manual in the CLI path.
- Report formatters produce the expected substrings.
- Existing suite stays green.

## Out of Scope / Future

Reuses holdings + live prices. A later issue could fold reward value into the
default price table / tax report if desired; this feature deliberately keeps it
within the `staking` command.
