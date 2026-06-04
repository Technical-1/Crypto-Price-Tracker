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
- **Cost-basis engine**: [`coinbasis`](https://pypi.org/project/coinbasis/) — multi-wallet ledger, lot matching, tax estimation
- **Market data & analytics**: [`cryptolytics`](https://pypi.org/project/cryptolytics/) — CoinGecko/DefiLlama/RSS access, rebalancing, performance, news
- **Data source**: CoinGecko public REST API (via `cryptolytics`)
- **Testing**: `pytest`
- **Linting**: `ruff`

This tool is a thin CLI: all business logic lives in the `coinbasis` and `cryptolytics`
packages. The app only handles argument parsing, file/config I/O (`appio.py`,
`appconfig.py`), and output formatting (`*_report.py`, `chart.py`).

## Getting Started

### Prerequisites

- Python 3.8+
- An internet connection (CoinGecko's public API needs no key)

### Installation

```bash
python3 -m pip install coinbasis cryptolytics
```

The two packages are the only runtime dependencies (declared in `pyproject.toml`).
For local development with editable installs, see the **Development** section below.

### Usage

```bash
python3 CryptoPriceTracker.py
```

With no arguments the tool prints the live per-coin profit table. When a `ledger.json`
file is present in the working directory (created by the `import` or `add` subcommands),
holdings are derived from it automatically. Otherwise the built-in `originalHoldings`
dictionary is used — edit the `total` and `cost` values there to match your own holdings.
Add more coins by extending the dictionary and the request URL.

## Commands

| Command | Description |
|---|---|
| `prices [--sparkline]` | Current prices + unrealized P/L (default view) |
| `holdings [--group {asset,wallet}] [--wallet NAME]` | Open lots per wallet |
| `valuation` | Portfolio value + allocation bar chart |
| `performance [--risk-free R]` | Sharpe, drawdown, cumulative return, sparkline |
| `migrate [--dry-run]` | Explicitly upgrade a V1 ledger to the coinbasis schema |

The existing `tax`, `rebalance`, `staking`, `news`, `history`, `import`, and `add`
commands remain available.

## Global Flags

These flags are accepted by every data command:

| Flag | Description |
|---|---|
| `--method {fifo,lifo,hifo,average,specific}` | Cost-basis lot-matching method (default `fifo`) |
| `--select FILE` | Lot-selection JSON file (required with `--method specific`) |
| `--wallet NAME` | Filter output to a single wallet |
| `--year YYYY` | Calendar-year filter (e.g. `--year 2024`) |
| `--offline` | Never fetch; use cached prices only |
| `--data-dir DIR` | Data directory (default: CWD; env: `CPT_DATA_DIR`) |

## CoinGecko API Key

Set `COINGECKO_API_KEY` to use a Demo or Pro API key. The tracker defaults to
keyless-first (no key required), escalating to the keyed endpoint only when
rate-limited (HTTP 429):

```bash
export COINGECKO_API_KEY=your-demo-key
export COINGECKO_PLAN=demo   # or "pro" for the Pro API
python3 CryptoPriceTracker.py prices
```

## Cost-Basis Method

Use `--method` on any command to choose FIFO (default), LIFO, HIFO, Average, or
Specific-ID:

```bash
python3 CryptoPriceTracker.py tax --method hifo --year 2024
python3 CryptoPriceTracker.py tax --method specific --select sel.json --year 2024
```

`--method specific` requires `--select FILE` (a lot-selection JSON file); without it
the command exits with a clear message pointing you at an automatic method.

## V1 Ledger Migration

If your `ledger.json` is in the old single-wallet flat format, it is upgraded
automatically the first time you run any command. The original is preserved at
`ledger.json.v1.bak`. Run `migrate --dry-run` first to preview the conversion:

```bash
python3 CryptoPriceTracker.py migrate --dry-run   # preview, writes nothing
python3 CryptoPriceTracker.py migrate             # upgrade in place + backup
```

After migration, `ledger.json` uses the coinbasis externally-tagged multi-wallet
schema (one `{"Buy": {...}}` / `{"Sell": {...}}` / `{"Income": {...}}` object per
entry, each with a `wallet` field).

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
the cost basis; sell fees are subtracted from proceeds. An optional `wallet` column is
accepted for multi-wallet ledgers (defaults to `default`).

### Ledger schema

`ledger.json` uses the coinbasis externally-tagged multi-wallet schema — a JSON array
of single-key objects, one per event:

```json
[
  {"Buy":  {"timestamp": "2023-01-01T00:00:00Z", "wallet": "default",
            "asset": "bitcoin", "quantity": "1", "unit_price": "20000", "fee": "0"}},
  {"Income": {"timestamp": "2023-06-01T00:00:00Z", "wallet": "default",
              "asset": "ethereum", "quantity": "2", "value": "4000", "source": "Staking"}}
]
```

Old single-wallet flat ledgers (`{"date", "coin", "action", "quantity", "price_usd",
"fee_usd"}` rows) are transparently upgraded on first use — see **V1 Ledger Migration**
above.

### Cost-basis methods

Pass `--method` to `tax` to select how lots are matched when you sell:

| Method | Flag | Behaviour |
|---|---|---|
| FIFO | `--method fifo` (default) | Oldest lots consumed first |
| LIFO | `--method lifo` | Newest lots consumed first |
| HIFO | `--method hifo` | Highest-cost lots consumed first |
| Average cost | `--method average` | Pooled average basis across all remaining lots |
| Specific-ID | `--method specific --select FILE` | Lots chosen explicitly from a selection JSON file |

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

## Staking & Yield

```bash
python3 CryptoPriceTracker.py staking [--days 365]
```

The `staking` subcommand prints four sections for your staked holdings:

1. **Staking yield** — projected yield over the chosen horizon (`--days`) per coin, showing APY %, source (API or manual), staked quantity, crypto yield, and USD equivalents (period and monthly).
2. **Realized staking rewards** — rewards loaded from `rewards.csv` summed per coin, valued at the current live price (zero-cost income), with a total USD value.
3. **Staked vs not staked** — extra annual USD income that staking provides relative to an unstaked position.
4. **Combined profit/loss** — portfolio unrealized profit (from the ledger) plus the realized reward value for a combined total.

### staking.json schema

Copy `staking.sample.json` to `staking.json` (git-ignored) and edit it to match your positions:

```json
{
  "ethereum": {"staked_qty": 2.0, "symbol": "ETH", "apy": 0.04},
  "stellar": {"staked_qty": 1000.0, "symbol": "XLM", "apy": 0.03}
}
```

| Field | Required | Description |
|---|---|---|
| `staked_qty` | Yes | Number of units currently staked (must be positive) |
| `symbol` | No | Ticker symbol used to look up APY from DefiLlama (e.g. `ETH`) |
| `apy` | No | Manual APY as a decimal (e.g. `0.04` = 4 %) — used as fallback when the API returns nothing |

APY is fetched best-effort from [DefiLlama yields](https://yields.llama.fi/pools), matched by `symbol`. For each symbol the pool with the highest TVL is chosen and its APY is used. If the API is unreachable or the symbol has no match, the manual `apy` field is used instead. DefiLlama includes DeFi liquidity pools as well as native protocol staking, so the figure is an approximation of on-chain staking yield rather than an exact protocol rate.

### rewards.csv schema

Copy `rewards.sample.csv` to `rewards.csv` (git-ignored) and append a row for every reward event:

```
date,coin,quantity
2024-01-15,ethereum,0.012
2024-02-15,ethereum,0.013
2024-02-20,stellar,25
```

| Column | Description |
|---|---|
| `date` | ISO date `YYYY-MM-DD` of the reward |
| `coin` | CoinGecko coin ID (e.g. `ethereum`, `stellar`) |
| `quantity` | Number of units received |

Realized rewards are valued at the **current** live price (treated as zero-cost income) and added to the portfolio's unrealized profit to produce the combined P/L total.

## News & Sentiment

```bash
python3 CryptoPriceTracker.py news [--coin ID] [--limit 5]
```

The `news` subcommand fetches recent headlines for each tracked coin (or one specific coin via `--coin`) and prints a per-coin block containing:

- A sentiment summary line: coin name, overall sentiment label, and bullish/bearish/neutral counts.
- Up to `--limit` dated headlines (default 5), each tagged bullish/bearish/neutral, with a clickable article URL on the following line.

### News sources

By default, news is pulled from keyless RSS feeds (no API key required). To use additional sources or customise behaviour, copy `news.sample.json` to `news.json` (git-ignored) and edit it:

```json
{
  "feeds": ["https://cointelegraph.com/rss"],
  "cryptopanic_token": "",
  "keywords": {
    "bitcoin": ["bitcoin", "btc"],
    "ethereum": ["ethereum", "eth"]
  }
}
```

| Field | Description |
|---|---|
| `feeds` | List of RSS feed URLs to pool. Replaces the built-in default if non-empty. |
| `cryptopanic_token` | Optional [CryptoPanic](https://cryptopanic.com/developers/api/) API token. When set, CryptoPanic results are pooled alongside RSS headlines. |
| `keywords` | Per-coin list of match terms. If a coin has no entry, its CoinGecko ID is used as the sole keyword. |

A feed that is unreachable, returns an HTTP error, or contains a DOCTYPE is skipped with a notice on stderr; remaining feeds still run.

### Headline filtering

Headlines are matched per coin using whole-word, case-insensitive keyword search against the title. For example, the keyword `eos` matches "EOS mainnet" but not "theos protocol", so coins with short or common identifiers can be disambiguated via the `keywords` config.

### Sentiment

Sentiment is classified by a naive keyword-lexicon heuristic, not machine learning. Each headline title is scanned for a fixed set of bullish words (e.g. "surge", "rally", "adoption", "bullish") and bearish words (e.g. "crash", "hack", "lawsuit", "bearish"). The label with the higher count wins; a tie or no match yields "neutral". The per-coin summary tallies all matched headlines and picks the majority label the same way.

### Security note

RSS feeds that declare a `<!DOCTYPE ...>` are rejected before parsing. The stdlib `xml.etree` does not resolve external entities (so XXE/SSRF is not exploitable), but a DOCTYPE with custom entity definitions is the vector for billion-laughs denial-of-service. Rejecting DOCTYPE keeps the project stdlib-only (no `defusedxml` dependency) while closing that vector.

## Historical Playback & Graphing

```bash
python3 CryptoPriceTracker.py history [--days 90] [--date YYYY-MM-DD] [--play]
```

The `history` subcommand reconstructs your portfolio's daily value and P/L over the chosen window and renders the result as a Unicode sparkline chart in the terminal.

### How reconstruction works

Rather than multiplying your *current* holdings by old prices, the command replays the ledger to determine exactly which coins you held on each historical day, then values those as-of holdings at that day's CoinGecko price. This means past P/L figures reflect what you actually owned at the time — buys made after a given day are excluded from that day's calculation.

### Output modes

| Flag | Behaviour |
|---|---|
| *(none)* | Prints two sparkline rows (Value and P/L) with a start/end/min/max/delta summary |
| `--play` | Also steps through each day in the window, one line per day, with a horizontal P/L bar |
| `--date YYYY-MM-DD` | Also prints a per-coin breakdown (quantity, price, value, P/L) for that specific day; if the exact date has no price data the nearest available day is used |

Days within the window that have at least one matching recent news headline are marked with `*` in the playback view. This is best-effort: RSS feeds carry only current headlines, so coverage of older dates is limited.

### Snapshots

Each run appends a snapshot row `{"date", "total_value", "cost", "pl"}` to `snapshots.jsonl` in the working directory. The file is git-ignored and accumulates over time so you can track portfolio history across multiple sessions.

### History window

Pass `--days N` to control how many days of price history are fetched from CoinGecko. Default is 90 days.

## Development

```bash
# Install the app plus the two packages in editable mode for local development
python3 -m pip install -e .
python3 -m pip install -e ../coinbasis -e ../cryptolytics   # if developing the packages too

# Run the test suite
python3 -m pytest

# Lint
python3 -m ruff check .
```

All tests mock the `coinbasis` and `cryptolytics` calls (no live CoinGecko/DefiLlama/RSS
network access), so the suite runs offline and deterministically.

## Project Structure

```
Crypto-Price-Tracker/
├── CryptoPriceTracker.py              # Entry point: argparse CLI + thin orchestrators over the packages
├── appio.py                           # All file/config I/O: ledger load/save, V1 migration, CSV import, snapshots
├── appconfig.py                       # Env/XDG → AppContext (the only place env vars are read)
├── report.py                          # Format prices, holdings, valuation, realized, unrealized, tax sections
├── rebalance_report.py                # Format allocation and trade sections
├── staking_report.py                  # Format staking yield + rewards sections
├── news_report.py                     # Format per-coin sentiment summary and headline list
├── history_report.py                  # Format chart, playback, and per-day snapshot output
├── perf_report.py                     # Format performance metrics + sparkline
├── chart.py                           # Unicode sparkline and horizontal-bar chart primitives
├── pyproject.toml                     # Project metadata + deps (coinbasis, cryptolytics)
├── taxconfig.json                     # US tax-rate preset (editable; missing/bad file falls back to defaults)
├── transactions.csv                   # Sample CSV import template
├── targets.sample.json                # Sample custom rebalancing targets (copy to targets.json to use)
├── staking.sample.json                # Sample staking config (copy to staking.json to use)
├── rewards.sample.csv                 # Sample staking rewards log (copy to rewards.csv to use)
├── news.sample.json                   # Sample news config (copy to news.json to use)
└── tests/
    ├── conftest.py                    # Shared fixtures: tmp_ledger, v1 ledger, MockClient
    ├── test_appio.py                  # Loaders, V1 migration, CSV import, snapshot round-trip
    ├── test_formatters.py             # All formatters with fixed package dataclasses (pure)
    ├── test_cli.py                    # Argparse builder + run_* dispatch + error paths (mocked packages)
    ├── test_chart.py                  # sparkline and hbar primitives
    └── test_integration.py            # End-to-end pipeline per command (mocked packages)
```

All cost-basis math, lot matching, tax estimation, market-data fetching, analytics,
staking, news, and history reconstruction now live in the `coinbasis` and `cryptolytics`
packages rather than in this repository.

## License

Unlicensed (personal project)

## Author

Jacob Kanfer — [GitHub](https://github.com/Technical-1)
