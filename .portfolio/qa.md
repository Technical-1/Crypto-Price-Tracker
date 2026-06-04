# Project Q&A

## Overview

Crypto-Price-Tracker is a command-line crypto portfolio tracker. From a single
transaction ledger it produces cost-basis tax reports, live valuations, rebalancing
plans, performance metrics, staking-yield projections, news with sentiment, and
historical playback. The app itself is a thin CLI: all accounting and analytics live in
two published PyPI packages — `coinbasis` (the cost-basis/tax engine) and `coinlytics`
(portfolio analytics + market data) — so the repository is just argument parsing,
file/config I/O, and output formatting.

## Problem Solved

Exchange dashboards rarely answer the questions that matter at tax time or when
rebalancing: what are my realized and unrealized gains, what tax do I owe under a given
lot-matching method, how far has my allocation drifted from target, and how has the
portfolio moved over time. This tool answers all of them from one ledger you control,
with FIFO/LIFO/HIFO/average/specific-ID cost basis and short/long-term classification.

## Target Users

- **Crypto holders preparing taxes** — anyone who needs realized-gain and estimated-tax reports across multiple wallets and lot-matching methods.
- **Active portfolio managers** — people who want rebalancing trades, risk analytics, and performance metrics without a paid dashboard.
- **Command-line users** — those who prefer a scriptable, pipeable tool that keeps its data in plain local files.

## Key Features

### Ledger-driven reporting
Every report derives from `ledger.json`. Seed it with `import FILE.csv` or `add`, then run any of the twelve subcommands (`prices`, `holdings`, `valuation`, `tax`, `rebalance`, `performance`, `staking`, `news`, `history`, `import`, `add`, `migrate`).

### Cost-basis & tax
The `tax` command prints realized gains (with short/long-term subtotals), unrealized P/L at live prices, and an estimated-tax section using the rates in `taxconfig.json`.

### Rebalancing & analytics
`rebalance` computes trades toward equal-weight, market-cap, or custom target allocations with a drift band, alongside volatility and correlation risk analytics. `performance` reports Sharpe, drawdown, and cumulative return with a sparkline.

### Resilient market data
Live prices come from CoinGecko through `coinlytics`, with last-good caching, a fully offline mode (`--offline`), and graceful handling of rate limits and missing prices.

## Technical Highlights

### Package decomposition keeps the app thin
The cost-basis/tax engine (`coinbasis`) and the analytics/market-data layer (`coinlytics`) are separate, versioned PyPI packages. `CryptoPriceTracker.py` only orchestrates: each `run_*` function loads data, calls the packages, and hands typed dataclasses to a formatter. There is no accounting or analytics math in this repository.

### Automatic V1 ledger migration with a backup
`appio.load_ledger` detects the legacy single-wallet flat schema and upgrades it in place to the `coinbasis` externally-tagged multi-wallet schema, writing a `ledger.json.v1.bak` backup first (`_auto_migrate`). `--no-migrate` opts out and `migrate --dry-run` previews the conversion, so existing ledgers keep working without manual steps and are always recoverable.

### One cost-basis method switcher for every command
`appconfig.build_context_from_env` resolves `--method` (and `--select` for specific-ID) a single time into the `AppContext`, mapping the string to a `coinbasis.CostBasisMethod` and loading a `LotSelection` when needed. Downstream orchestrators just use the resolved method, so FIFO/LIFO/HIFO/average/specific behave identically across `tax`, `holdings`, `valuation`, and the rest.

### Resilient, offline-capable market data
Prices flow through a `coinlytics.CoinGeckoClient` configured in `appconfig.py`. `--offline` sets a max cache TTL so the client never hits the network and returns a stale `PriceBook` instead; live runs note staleness on stderr, and typed errors (`RateLimitedError`, `PriceSourceError`, `FeedError`, `StakingError`) are mapped in one `_dispatch` site to clear messages and exit codes rather than tracebacks.

## Engineering Decisions

### Reusable packages vs. a single script
- **Constraint**: The accounting and analytics logic is reusable and was outgrowing a one-file utility.
- **Options**: Keep everything in one script; split into local modules; or extract into independently published packages.
- **Choice**: Extract `coinbasis` and `coinlytics` as PyPI packages the app depends on.
- **Why**: The engine and analytics can be tested and versioned on their own while the app stays a thin, focused CLI.

### Single I/O boundary
- **Constraint**: File formats, env wiring, and schema translation are app concerns, not library concerns.
- **Options**: Read files and env vars wherever convenient, or funnel them through one place.
- **Choice**: All file/config I/O in `appio.py` and all env/XDG resolution in `appconfig.py`; the packages receive plain typed inputs.
- **Why**: The data contract is explicit and the packages stay free of filesystem and environment assumptions.

### Migrate-on-load vs. require a manual step
- **Constraint**: Legacy V1 ledgers are incompatible with the multi-wallet event schema.
- **Options**: Refuse to run until the user migrates, or upgrade transparently.
- **Choice**: Auto-migrate on first use with a `.v1.bak` backup, plus an explicit `migrate` command and `--no-migrate` escape hatch.
- **Why**: Existing users keep working with zero friction while the original file remains recoverable.

## Frequently Asked Questions

### How do I install and run it?
`python3 -m pip install .` installs the app plus `coinbasis` and `coinlytics` and gives you a `crypto-price-tracker` command. You can also run `python3 CryptoPriceTracker.py` directly once the two packages are importable.

### How do I get my transactions in?
Use `import FILE.csv` to bulk-import (columns `date,coin,action,quantity,price_usd,fee_usd`, with optional `wallet`), or `add` to enter one transaction interactively. Both append to `ledger.json`.

### Which cost-basis methods are supported?
FIFO (default), LIFO, HIFO, average-cost, and specific-ID via `--method`. Specific-ID requires `--select FILE`, a lot-selection JSON; without it the command exits with a message pointing you at an automatic method.

### Do I need a CoinGecko API key?
No. The tool uses CoinGecko's keyless endpoints by default. Set `COINGECKO_API_KEY` (and optionally `COINGECKO_PLAN`) to use a Demo or Pro key for higher limits.

### What happens if I'm offline or rate-limited?
Pass `--offline` to serve only cached prices. When live and rate-limited, the run uses the last-good cache where possible (noted on stderr) or exits with a clear `Rate limited by CoinGecko…` message instead of a traceback.

### My ledger is in the old format — will it still work?
Yes. It is upgraded to the current multi-wallet schema automatically on first use, with the original kept at `ledger.json.v1.bak`. Run `migrate --dry-run` first if you want to preview the conversion.
