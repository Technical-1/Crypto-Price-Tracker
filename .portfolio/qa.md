# Project Q&A

## Overview

Crypto-Price-Tracker is a small Python command-line tool that prints the live profit/loss on a cryptocurrency portfolio, one coin at a time. It pulls current USD prices and 24-hour change from the CoinGecko API and renders an aligned terminal table of profit, cost basis, and daily movement. The interesting part is how much robustness lives in such a small file: it stays useful even when an exchange API rate-limits it or quietly drops a coin.

## Problem Solved

Exchange apps like Coinbase historically didn't show a clear overall profit/loss across everything you hold. This tool answers a single question directly: for each coin I own, given what I paid, am I up or down right now — and by how much?

## Target Users

- **Individual crypto holders** — anyone who wants a quick, at-a-glance profit number per coin without logging into an exchange dashboard.
- **Tinkerers** — people comfortable editing a Python dictionary to track their own coins and cost basis, and extending the list over time.

## Key Features

### Per-coin profit table
For every holding, the tool prints profit, cost basis, and 24-hour percentage change in a fixed-width table, computed from current CoinGecko prices.

### Resilient pricing
Missing, delisted, or price-less coins are skipped with a notice on stderr; network failures and rate limits end with a clear message and a non-zero exit code instead of a stack trace.

### Editable holdings
A single dictionary defines the tracked coins and their cost basis. Adding a coin means adding its CoinGecko ID to the request and the dictionary.

## Technical Highlights

### Turning a rate-limit into a clear error, not a mystery crash
CoinGecko returns valid JSON even for a 429 rate-limit response, so naively parsing it would let the program run on and fail later with a confusing `KeyError` deep in the print loop. `fetch_prices` calls `raise_for_status()` (and sets a request timeout); `main` catches `requests.RequestException`, prints a readable message, and exits 1. The failure is reported at its true cause — the request — rather than as unrelated downstream noise.

### Graceful degradation when a coin disappears
Coin IDs get renamed or delisted, so a healthy response can simply omit a coin you track. The print loop looks coins up with `.get` and treats both a missing entry and a null/absent `usd` value as "skip this row, note it on stderr, keep going" (`CryptoPriceTracker.py:62`). One bad coin never blanks out the rest of the report.

### Pure, testable profit math with a divide-by-zero guard
`compute_profit` (`CryptoPriceTracker.py:38`) is a pure function: it computes `(price - cost/total) * total` and returns `None` when `total <= 0`, which is the realistic failure mode for a hand-edited holdings dictionary. Keeping it free of I/O means the arithmetic — including the multi-coin average-cost case — is verified directly in the test suite.

### Output you can pipe
Skip notices and errors are written to stderr while only data rows go to stdout, so `python CryptoPriceTracker.py > table.txt` produces a clean data file with diagnostics still visible on the terminal.

## Engineering Decisions

### Single file with functions vs. a flat script vs. a package
- **Constraint**: The tool needed to become testable, but it's fundamentally a one-file utility.
- **Options**: Leave it as a flat top-level script (untestable, runs HTTP on import); restructure into a multi-module package (heavy for the scope); or split into functions behind a `__main__` guard.
- **Choice**: Functions (`fetch_prices`, `compute_profit`, `main`) in one importable module.
- **Why**: It unlocks unit testing of both network and arithmetic paths without the ceremony of packaging something this small.

### Skip-and-continue vs. fail-fast on per-coin data
- **Constraint**: External coin IDs change without warning.
- **Options**: Abort the whole run on the first missing coin, or skip just the affected coins.
- **Choice**: Skip the affected coin with an stderr notice and continue.
- **Why**: A portfolio report is most useful when one delisted coin doesn't hide every other coin's profit.

### Float-formatted cost basis
- **Constraint**: Real cost bases are rarely whole dollars.
- **Options**: Format cost as an integer (compact, but truncates `19.99` to `19`), or as a fixed-point float.
- **Choice**: Format the cost column with two decimals.
- **Why**: Accurate cost display matters more than a slightly narrower column; truncation silently misreports what the user paid.

## Frequently Asked Questions

### How do I track my own coins and amounts?
Edit the `originalHoldings` dictionary in `CryptoPriceTracker.py`, setting each coin's `total` (how many units you hold) and `cost` (what you paid in total). To add a coin, include its CoinGecko ID both in the dictionary and in the `ids=` list of the request URL.

### Do I need a CoinGecko API key?
No. The tool uses CoinGecko's public `simple/price` endpoint, which requires no authentication.

### What happens if CoinGecko rate-limits me or is down?
The request raises, `main` catches it, prints `Failed to fetch prices from CoinGecko: …` to stderr, and exits with code 1 — no partial or misleading output.

### Why did one of my coins not show up in the table?
CoinGecko didn't return a usable price for it (often because the coin's ID was renamed or delisted). That coin is skipped and a `(skipped …)` notice is printed to stderr; the rest of your coins still appear.

### How is "profit" calculated?
Average cost is `cost / total`; profit is `(current_price - average_cost) * total`. So it reflects your total gain or loss on that holding at the current USD price.

### Can I save the table to a file?
Yes. Because only data rows go to stdout, `python CryptoPriceTracker.py > table.txt` captures a clean table while skip notices and errors remain on stderr.

### How do I run the tests?
Install dev dependencies with `python3 -m pip install -r requirements-dev.txt`, then run `python3 -m pytest`. The suite covers price fetching, the profit math, and each skip/error path.
