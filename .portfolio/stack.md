# Tech Stack

## Core Technologies

| Category | Technology | Version | Why this choice |
|----------|------------|---------|-----------------|
| Language | Python | 3.10+ | Modern typing (`X \| Y`, `list[...]`) and a portable, dependency-light CLI runtime |
| Cost-basis engine | `coinbasis` | >=0.1,<0.2 | Pure-Python lot-matching and tax engine; keeps all accounting math out of the app |
| Market data & analytics | `coinlytics` | >=0.1,<0.2 | CoinGecko/DefiLlama/RSS access plus rebalancing, performance, staking, and news analytics |
| Data source | CoinGecko REST API | (via `coinlytics`) | Keyless-first prices, history, and market caps for many coins per call |

## Backend

- **Runtime**: Python CLI (no server) — `crypto-price-tracker` console script (entry point `CryptoPriceTracker:cli`)
- **Architecture**: Thin CLI orchestrating two PyPI packages; the app handles argument parsing, file/config I/O, and output formatting only
- **Auth**: None required for CoinGecko's public endpoints; optional `COINGECKO_API_KEY` (Demo/Pro) read from the environment

## Infrastructure

- **Hosting**: None — runs locally from the command line
- **Storage**: Local files in the working directory (`ledger.json`, `taxconfig.json`, `targets.json`, `staking.json`, `rewards.csv`, `news.json`, `snapshots.jsonl`); price cache under the XDG cache dir
- **CI/CD**: None

## Development Tools

- **Build/Packaging**: setuptools (`pyproject.toml`); module-based layout with a `crypto-price-tracker` console entry point
- **Package Manager**: `pip` with `requirements.txt` / `requirements-dev.txt`
- **Testing**: `pytest` — formatters, loaders/migration, CLI dispatch, and end-to-end pipelines with the packages mocked (runs fully offline)
- **Linting**: `ruff`

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `coinbasis` | Cost-basis/tax engine: builds a `Portfolio` from the ledger and computes holdings, realized gains, unrealized P/L, and tax estimates under FIFO/LIFO/HIFO/average/specific |
| `coinlytics` | Analytics + market data: CoinGecko client (prices, history, market caps), rebalancing, performance metrics, staking yields, and news/sentiment |
