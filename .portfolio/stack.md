# Tech Stack

## Core Technologies

| Category | Technology | Version | Why this choice |
|----------|------------|---------|-----------------|
| Language | Python | 3.8+ | Batteries-included standard library and the simplest path to a portable CLI utility |
| HTTP client | `requests` | >=2.32,<3 | De-facto standard for HTTP in Python; built-in timeout, status helpers, and a clean exception hierarchy |
| Data source | CoinGecko REST API | `simple/price` | Free, keyless endpoint that returns price and 24h change for many coins in one call |

## Backend

- **Runtime**: Python 3 CLI script (no server)
- **API Style**: Consumes a REST endpoint; one batched GET per run
- **Auth**: None — CoinGecko's public price endpoint requires no key

## Infrastructure

- **Hosting**: None — runs locally from the command line
- **CI/CD**: None
- **Monitoring**: None (single-shot script)

## Development Tools

- **Package Manager**: `pip` with pinned `requirements.txt` / `requirements-dev.txt`
- **Testing**: `pytest` (>=9,<10) — 12 tests covering fetch behavior, profit math, and the skip paths
- **Linting**: `pyflakes` (>=3,<4) — catches unused imports and undefined names

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | Fetch prices from CoinGecko with a timeout and HTTP status checking |
| `pytest` | Run the test suite, including `capsys`-based checks of stdout/stderr behavior |
| `pyflakes` | Verify the module has no unused imports or undefined names |
