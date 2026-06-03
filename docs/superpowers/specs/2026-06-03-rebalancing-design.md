# Portfolio Optimization & Rebalancing — Design Spec

**Issue:** #2 — Add Portfolio Optimization & Rebalancing Suggestions
**Date:** 2026-06-03
**Author:** Jacob Kanfer

## Context

`Crypto-Price-Tracker` is a dependency-light Python CLI. Issue #1 (tax &
cost-basis) added a transaction ledger that is now the source of truth for
holdings (`holdings.py`), plus the resilient CoinGecko fetch pattern in
`CryptoPriceTracker.py`. This feature analyzes the portfolio's allocation and
risk and suggests rebalancing trades toward a target allocation, with a simple
historical what-if comparison. It stays CLI-native and dependency-light
(`requests` + stdlib only: `statistics`, `math`, `json`).

Decisions locked in during brainstorming:

- **Risk analytics:** full — per-coin volatility AND a correlation matrix AND
  overall portfolio volatility (needs historical daily prices).
- **Targets:** config presets (`equal`, `marketcap`) plus user-defined custom
  targets in `targets.json`.
- **Backtest:** include a simple buy-and-hold what-if comparison over the
  fetched window.

## Goals

1. Show current allocation (value and % per held coin) from live prices.
2. Compute per-coin volatility (stdev of daily returns, shown daily and
   annualized), a correlation matrix, and overall portfolio volatility.
3. Suggest target allocations via `equal`, `marketcap`, or `custom` strategies
   and output the buy/sell trades to reach the chosen target.
4. Show a simple buy-and-hold backtest comparing current vs target weights over
   the historical window.

## Non-Goals

- Risk-based optimization (min-variance / risk-parity solvers).
- A web/GUI frontend, charts, or images.
- Intraday/tick data; only daily closes from CoinGecko.
- Multi-currency (USD only).

## Architecture

New stdlib-only modules around the existing code, reusing `holdings.py` and the
existing fetch ethos. `requests` remains the only pip dependency.

```
marketdata.py         # fetch_history(coin, days) -> [(date, price)]; fetch_market_caps(ids) -> {coin: mcap}
analytics.py          # daily_returns, volatility, correlation_matrix, portfolio_volatility
rebalance.py          # target_weights(strategy, ...), load_targets(path), compute_trades(...)
backtest.py           # buy_and_hold_return(history, weights) over the window
rebalance_report.py   # format allocation / risk / correlation / trades / backtest tables (return strings)
CryptoPriceTracker.py # new `rebalance [--strategy equal|marketcap|custom] [--days 90]` subcommand
targets.sample.json   # committed sample of custom target weights
```

Tax formatting stays in `report.py`; rebalance formatting lives in
`rebalance_report.py` so neither file sprawls.

## Data Sources (CoinGecko)

- **Live prices** (current value): existing batched `fetch_prices` (USD).
- **Historical daily prices**: `/coins/{id}/market_chart?vs_currency=usd&days={days}&interval=daily`,
  one call per held coin. Response `prices` is `[[ms_timestamp, price], ...]`;
  reduced to a list of `(YYYY-MM-DD, price)` daily points.
- **Market caps** (for `marketcap` strategy): batched `simple/price` with
  `include_market_cap=true`, parsed as `{coin: usd_market_cap}`.

## Components

### marketdata.py

- `fetch_history(coin, days=90, timeout=10)` → `list[(date_str, float)]`.
  Raises `requests.RequestException` on network/HTTP failure (caller handles).
- `fetch_market_caps(ids, timeout=10)` → `{coin: market_cap_usd}`.
- Both build URLs internally and use `raise_for_status()`, mirroring
  `fetch_prices`.

### analytics.py (pure functions, no network)

- `daily_returns(prices)` → simple returns `[(p[i]/p[i-1]) - 1, ...]` from a
  price list. Fewer than 2 prices → `[]`.
- `volatility(returns)` → `statistics.pstdev(returns)` (daily). `annualize(v)` →
  `v * sqrt(365)`. Both return `0.0` for empty/singleton input.
- `correlation(returns_a, returns_b)` → Pearson correlation computed directly
  (covariance over the product of standard deviations) on the overlapping prefix;
  a constant (zero-variance) series yields `0.0`.
- `correlation_matrix(returns_by_coin)` → `{(a, b): corr}` for all pairs
  (diagonal 1.0).
- `portfolio_volatility(weights, vols, corr)` → `sqrt(Σ_i Σ_j w_i w_j σ_i σ_j ρ_ij)`.

### rebalance.py

- `target_weights(strategy, coins, market_caps=None, custom=None)` →
  `{coin: weight}` summing to 1.0:
  - `equal`: `1/N` over the held coins.
  - `marketcap`: `mcap_i / Σ mcap` (skips coins with missing/zero cap, renormalizes).
  - `custom`: the validated `custom` dict.
- `load_targets(path)` → dict of `{coin: fraction}`; raises `ValueError` if the
  file is missing, malformed, or the weights do not sum to ≈1.0 (tolerance 1e-6).
- `compute_trades(current_values, target_weights, prices)` → per coin:
  `delta_usd = weight*total − current_value`; `action` buy/sell; `coin_amount =
  delta_usd / price`. Total is `Σ current_values`. Coins held but absent from the
  target get weight 0 (full sell); coins in the target but unheld are bought from 0.

### backtest.py

- `buy_and_hold_return(history_by_coin, weights)` → fractional return over the
  window: `Σ_i w_i (price_end_i / price_start_i − 1)`, using the first and last
  available daily price per coin. Coins lacking history are skipped and their
  weight is renormalized across the rest (documented).

### rebalance_report.py (return strings, no I/O)

1. `format_allocation(current_values)` — coin, value, %.
2. `format_risk(vols_daily, vols_annual, portfolio_vol)` — per-coin and total.
3. `format_correlation(coins, corr)` — labeled NxN matrix.
4. `format_trades(trades)` — coin, action, USD delta, coin amount, target %.
5. `format_backtest(window_days, current_return, target_return, strategy)` —
   side-by-side window returns.

## CLI Surface

```
python3 CryptoPriceTracker.py rebalance [--strategy equal|marketcap|custom] [--days 90]
```

Default `--strategy equal`, `--days 90`. The command:

1. Loads holdings from the ledger (error+exit if empty).
2. Fetches live prices; builds current allocation.
3. Fetches per-coin history; computes risk (volatility, correlation, portfolio
   volatility).
4. Builds target weights for the chosen strategy and computes trades.
5. Runs the backtest (current vs target weights).
6. Prints the five sections.

The existing default (no-arg) behavior and other subcommands are unchanged.

## Error Handling

- A coin whose history fetch fails or returns too few points is skipped with a
  stderr notice; risk/correlation/backtest compute over the remaining coins.
- If fewer than 2 coins have usable history, the correlation matrix and
  portfolio volatility are skipped with a clear note; allocation, per-coin
  volatility (where available), trades, and (where possible) backtest still print.
- Empty ledger → clear message, exit 1.
- `--strategy custom` with a missing/malformed `targets.json` or weights not
  summing to ≈1.0 → clear error, exit 1.
- `--strategy marketcap` when market-cap data is unavailable → clear error / fall
  back message, exit 1.
- Live-price or all-history network failures reuse the existing readable-message,
  non-zero-exit handling.

## Testing

`pytest`, no network (mock `fetch_prices`, `fetch_history`, `fetch_market_caps`).
Coverage:

- `daily_returns` / `volatility` on a known series (hand-computed expected values).
- `correlation`: perfectly correlated series → 1.0; anti-correlated → −1.0;
  constant series → 0.0.
- `portfolio_volatility` on a 2-asset case with known weights/vols/correlation.
- `target_weights` for equal, marketcap (incl. missing-cap renormalization), and
  custom.
- `load_targets`: valid file; missing file; weights not summing to 1 → error.
- `compute_trades`: rebalance up/down, a coin to fully sell (target 0), a coin
  bought from zero.
- `buy_and_hold_return` on a known 2-coin window; coin-missing-history renormalization.
- Graceful skips: a coin missing history; fewer than 2 coins with history.
- `rebalance_report` formatters produce the expected substrings.
- Existing suite stays green.

## Out of Scope / Future

Reuses the ledger + holdings modules from issue #1. The historical-fetch helper
in `marketdata.py` will likely be reused by issue #5 (historical playback).
