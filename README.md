# Crypto-Price-Tracker

A small command-line tool that shows the live profit/loss on a cryptocurrency portfolio, coin by coin.

Coinbase didn't give me a clear overall profit figure for the coins I held, so I built a script that pulls current prices from the CoinGecko API and prints a per-coin table of profit, cost basis, and 24-hour change. It's deliberately a single, dependency-light Python file you can drop your own holdings into.

## Features

- **Per-coin profit table** — for each holding it prints profit, cost basis, and 24-hour price change in an aligned terminal table.
- **Live pricing via CoinGecko** — one batched request fetches USD prices and 24h change for every tracked coin at once.
- **Resilient to bad data** — coins that CoinGecko has delisted or returns without a price are skipped with a notice on stderr instead of crashing the run.
- **Clear network failures** — rate limits, timeouts, and HTTP errors produce a readable message and a non-zero exit code, never a raw traceback.
- **Bring your own holdings** — edit one dictionary to set your totals and cost basis; add coins by extending the dictionary and the request.

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

Edit the `total` and `cost` values in the `originalHoldings` dictionary in
`CryptoPriceTracker.py` to match your own holdings. Add more coins by adding their
CoinGecko IDs to both the request URL and the dictionary. Coins that CoinGecko no
longer returns are skipped with a notice on stderr rather than crashing.

## Development

```bash
# Install runtime + dev dependencies
python3 -m pip install -r requirements-dev.txt

# Run the test suite
python3 -m pytest

# Lint for unused imports / undefined names
python3 -m pyflakes CryptoPriceTracker.py
```

## Project Structure

```
Crypto-Price-Tracker/
├── CryptoPriceTracker.py              # Entry point: fetch prices, compute profit, print table
├── tests/
│   └── test_crypto_price_tracker.py   # pytest suite covering fetch, profit math, and skip paths
├── requirements.txt                   # Runtime dependency (requests)
└── requirements-dev.txt               # Dev/test dependencies (pytest, pyflakes)
```

## License

Unlicensed (personal project)

## Author

Jacob Kanfer — [GitHub](https://github.com/Technical-1)
