# Crypto-Price-Tracker

A small command-line tool that shows the live profit/loss on a cryptocurrency portfolio, coin by coin.

Coinbase didn't give me a clear overall profit figure for the coins I held, so I built a script that pulls current prices from the CoinGecko API and prints a per-coin table of profit, cost basis, and 24-hour change. It's deliberately a single, dependency-light Python file you can drop your own holdings into.

## Features

- **Per-coin profit table** — for each holding it prints profit, cost basis, and 24-hour price change in an aligned terminal table.
- **Live pricing via CoinGecko** — one batched request fetches USD prices and 24h change for every tracked coin at once.
- **Resilient to bad data** — coins that CoinGecko has delisted or returns without a price are skipped with a notice on stderr instead of crashing the run.
- **Clear network failures** — rate limits, timeouts, and HTTP errors produce a readable message and a non-zero exit code, never a raw traceback.
- **Bring your own holdings** — edit one dictionary to set your totals and cost basis; add coins by extending the dictionary and the request.
- **Tax & cost-basis analysis** — import transactions from CSV, or enter them interactively, then run a full tax report with FIFO, LIFO, or average-cost lot matching.

## Tech Stack

- **Language**: Python 3
- **HTTP**: `requests`
- **Data source**: CoinGecko public REST API
- **Testing**: `pytest`
- **Linting**: `pyflakes`

## Getting Started

### Prerequisites

- Python 3.8+
- An internet connection (CoinGecko's public API needs no key)

### Installation

```bash
python3 -m pip install -r requirements.txt
```

### Usage

```bash
python3 CryptoPriceTracker.py
```

With no arguments the tool prints the live per-coin profit table. When a `ledger.json`
file is present in the working directory (created by the `import` or `add` subcommands),
holdings are derived from it automatically. Otherwise the built-in `originalHoldings`
dictionary is used — edit the `total` and `cost` values there to match your own holdings.
Add more coins by extending the dictionary and the request URL.

## Tax & Cost-Basis

### Subcommands

```bash
# Import transactions from a CSV file into the ledger
python3 CryptoPriceTracker.py import FILE.csv

# Interactively enter one transaction and append it to the ledger
python3 CryptoPriceTracker.py add

# Print a full tax report (realized gains, unrealized P/L, estimated tax)
python3 CryptoPriceTracker.py tax [--method fifo|lifo|average] [--year YYYY]
```

The `tax` subcommand prints three sections:

1. **Realized gains/losses** — every disposal with proceeds, cost basis, gain, and short/long-term classification.
2. **Unrealized P/L** — current holdings valued at live CoinGecko prices versus your cost basis.
3. **Estimated tax** — applied at the rates configured in `taxconfig.json`.

### CSV format

Transactions are imported from a CSV file with the following header:

```
date,coin,action,quantity,price_usd,fee_usd
```

| Column | Description |
|---|---|
| `date` | ISO date `YYYY-MM-DD` |
| `coin` | CoinGecko coin ID (e.g. `bitcoin`, `ethereum`) |
| `action` | `buy` or `sell` |
| `quantity` | Number of units (fractional values supported) |
| `price_usd` | Price **per unit** in USD at the time of the transaction |
| `fee_usd` | Transaction fee in USD (can be 0) |

A `transactions.csv` sample template is included in the repository. Buy fees are added to
the cost basis; sell fees are subtracted from proceeds.

### Cost-basis methods

Pass `--method` to `tax` to select how lots are matched when you sell:

| Method | Flag | Behaviour |
|---|---|---|
| FIFO | `--method fifo` (default) | Oldest lots consumed first |
| LIFO | `--method lifo` | Newest lots consumed first |
| Average cost | `--method average` | Pooled average basis across all remaining lots |

Holdings held more than 365 days at the time of sale are classified long-term; 365 days or
fewer are short-term.

### Tax configuration

`taxconfig.json` ships with a US preset (0 % / 15 % / 20 % long-term brackets, 35 %
short-term rate). Edit it to match your actual situation. If the file is missing or
malformed, the tool falls back to documented defaults and prints a warning to stderr.

To filter the tax report to a single tax year:

```bash
python3 CryptoPriceTracker.py tax --year 2024
```

## Portfolio Rebalancing

```bash
python3 CryptoPriceTracker.py rebalance [--strategy equal|marketcap|custom] [--days 90]
```

The `rebalance` subcommand prints five sections for your current portfolio:

1. **Current allocation** — each coin's USD value and percentage of the portfolio.
2. **Risk (volatility)** — per-coin daily and annualized volatility (population stdev of daily returns). Portfolio volatility is also shown when at least two coins have sufficient price history. The correlation/portfolio-volatility section is skipped if fewer than two coins have history.
3. **Correlation matrix** — pairwise Pearson correlation among holdings, shown when at least two coins have history.
4. **Rebalancing trades** — buy/sell amounts (in USD and coin units) needed to reach the target allocation, keeping total portfolio value constant.
5. **Backtest** — simple buy-and-hold return over the chosen window (`--days`) for both your current weights and the target weights, so you can see how each would have performed.

### Strategies

| Flag | Behaviour |
|---|---|
| `--strategy equal` (default) | Equal weight across all holdings |
| `--strategy marketcap` | Weight proportional to live CoinGecko market cap |
| `--strategy custom` | Weights loaded from `targets.json` in the working directory |

### Custom targets

Copy `targets.sample.json` to `targets.json` and edit it to set your desired weights:

```json
{
  "bitcoin": 0.4,
  "ethereum": 0.3,
  "stellar": 0.2,
  "uniswap": 0.1
}
```

Weights must sum to exactly 1.0 (tolerance ±1e-6). `targets.json` is git-ignored — it is a runtime file, not committed.

### History window

Pass `--days N` to control how many days of price history are fetched from CoinGecko for the volatility and backtest calculations. Default is 90 days.

## Development

```bash
# Install runtime + dev dependencies
python3 -m pip install -r requirements-dev.txt

# Run the test suite
python3 -m pytest

# Lint for unused imports / undefined names
python3 -m pyflakes CryptoPriceTracker.py ledger.py costbasis.py holdings.py tax.py report.py analytics.py rebalance.py backtest.py marketdata.py rebalance_report.py
```

## Project Structure

```
Crypto-Price-Tracker/
├── CryptoPriceTracker.py              # Entry point: argparse CLI, fetch prices, compute profit, print table
├── ledger.py                          # Transaction dataclass, validation, JSON load/save, CSV import, interactive add
├── costbasis.py                       # Lot matching: FIFO, LIFO, average cost; produces Disposal records
├── holdings.py                        # Derives current holdings from ledger; falls back to built-in dict
├── tax.py                             # Tax config loading, realized-gain summary, and tax liability estimate
├── report.py                          # Formats realized, unrealized, and tax sections as text
├── analytics.py                       # Pure risk math: daily returns, volatility, correlation, portfolio volatility
├── rebalance.py                       # Target-weight strategies (equal, marketcap, custom) and trade computation
├── backtest.py                        # Buy-and-hold backtest over a price history window
├── marketdata.py                      # Historical price and market-cap fetching from CoinGecko
├── rebalance_report.py                # Format allocation, risk, correlation, trades, and backtest sections
├── taxconfig.json                     # US tax-rate preset (editable; missing/bad file falls back to defaults)
├── transactions.csv                   # Sample CSV import template
├── targets.sample.json                # Sample custom rebalancing targets (copy to targets.json to use)
├── tests/
│   ├── test_crypto_price_tracker.py   # Original suite: fetch, profit math, skip paths
│   ├── test_ledger.py                 # Ledger validation, JSON round-trip, CSV import, interactive add
│   ├── test_costbasis.py              # FIFO, LIFO, average, fees, long/short-term, oversell
│   ├── test_holdings.py               # Holdings derivation and ledger-or-default loading
│   ├── test_tax.py                    # Config loading, summarize, progressive brackets, tax floors
│   ├── test_report.py                 # Format helpers for realized, unrealized, and tax sections
│   ├── test_cli.py                    # Argparse builder and run_tax / run_rebalance integration
│   ├── test_analytics.py              # daily_returns, volatility, correlation, portfolio_volatility
│   ├── test_rebalance.py              # target_weights, load_targets, compute_trades
│   ├── test_backtest.py               # buy_and_hold_return with renormalization
│   ├── test_marketdata.py             # fetch_history, fetch_market_caps (mocked network)
│   └── test_rebalance_report.py       # format_* helpers for all five report sections
├── requirements.txt                   # Runtime dependency (requests)
└── requirements-dev.txt               # Dev/test dependencies (pytest, pyflakes)
```

## License

Unlicensed (personal project)

## Author

Jacob Kanfer — [GitHub](https://github.com/Technical-1)
