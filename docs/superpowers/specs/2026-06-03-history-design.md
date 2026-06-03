# Advanced Graphing & Historical Playback — Design Spec

**Issue:** #5 — Implement Advanced Graphing & Historical Playback
**Date:** 2026-06-03
**Author:** Jacob Kanfer

## Context

`Crypto-Price-Tracker` is a dependency-light Python CLI. Issues #1–#4 added a
ledger/holdings model (`holdings.py`, `costbasis.py`), historical-price fetching
(`marketdata.fetch_history`), and a news feed (`news_source.py`/`news.py`). This
feature reconstructs the portfolio's value and profit/loss over time, renders it
as a terminal chart, lets the user scrub through days, persists snapshots, and
marks days that have recent news. It stays CLI-native and dependency-light
(`requests` + stdlib only: `json`, `datetime`).

Decisions locked in during brainstorming:

- **History data:** reconstruct an accurate daily series on demand (CoinGecko
  historical prices + ledger replay) AND append a snapshot of the current state
  to `snapshots.jsonl` on each run.
- **Render/navigation:** a Unicode/ASCII chart plus `--date` (jump to a day's
  detail) and `--play` (step through days) — the CLI equivalent of a slider +
  interactive chart.
- **News overlay:** best-effort recent-news markers on the timeline (RSS has no
  archive, so only recent days get marked; documented).

## Goals

1. Reconstruct a daily `{date, value, cost, pl}` series over a window, valuing
   holdings *as of each day* (ledger replay) at that day's historical price.
2. Render the series as a terminal sparkline chart with a summary.
3. Step through the series day-by-day (`--play`) and jump to a single day's
   detailed snapshot (`--date`).
4. Append a current-state snapshot to `snapshots.jsonl` each run.
5. Mark days within the window that have recent news (best-effort).

## Non-Goals

- A web/GUI frontend, Chart.js/D3, or image output.
- A historical news archive (RSS provides only recent items).
- Intraday/hourly granularity (daily closes from CoinGecko only).
- Modifying existing features or their output.

## Architecture

New stdlib-only modules; reuses `holdings`, `costbasis`, `marketdata`,
`news_source`/`news`. `requests` remains the only pip dependency.

```
history.py         # holdings_as_of, reconstruct_series, make_snapshot,
                   #   append_snapshot, load_snapshots
chart.py           # sparkline(values), hbar(value, max_abs, width)  (pure)
history_report.py  # format_chart, format_playback, format_snapshot  (return strings)
CryptoPriceTracker.py  # new `history [--days 90] [--date YYYY-MM-DD] [--play]` subcommand
```

## Components

### history.py

- `holdings_as_of(txns, date, method="fifo")` → `{coin: {"total", "cost"}}`:
  derive holdings from only the transactions with `t.date <= date` (delegates to
  `holdings.derive_holdings` on the filtered list). A buy/sell dated after the
  cutoff is excluded.
- `reconstruct_series(txns, price_by_coin_date, dates, method="fifo")` →
  `list[{date, value, cost, pl}]`: for each date in `dates` (sorted), compute the
  as-of holdings and value each coin at `price_by_coin_date[coin][date]`. Coins
  with no price for that date are skipped for that day. `value` = Σ qty·price;
  `cost` = Σ remaining cost basis of the valued coins; `pl` = value − cost.
- `make_snapshot(holdings, prices, date)` → `{date, total_value, cost, pl}` from
  current holdings and live prices (`prices` = `{coin: {"usd": float}}`); coins
  without a live price are skipped.
- `append_snapshot(path, snapshot)` — append one JSON object per line (JSONL).
- `load_snapshots(path)` → `list[snapshot]`; missing file → `[]`.

`price_by_coin_date` is `{coin: {date_str: price}}`, built in the CLI from
`marketdata.fetch_history` per coin.

### chart.py (pure)

- `sparkline(values)` → a string of Unicode block glyphs (`▁▂▃▄▅▆▇█`) scaled
  min→max. Empty list → `""`; a single value (or all-equal) → one mid-level glyph
  per value.
- `hbar(value, max_abs, width)` → a horizontal bar string scaled to `width`
  against `max_abs`, handling negatives (e.g. a leading sign / direction). Zero or
  `max_abs <= 0` → empty bar.

### history_report.py (return strings, no I/O)

- `format_chart(series)` → a value sparkline, a P/L sparkline, and a start / end /
  min / max / Δ summary.
- `format_playback(series, news_dates)` → one line per day: `date  value  pl
  [hbar]` with a trailing `*` on days whose date is in `news_dates`.
- `format_snapshot(date, rows, total_value, total_pl)` → a per-coin breakdown for
  one day (`rows` = list of `{coin, qty, price, value, pl}`), with the day total.

## CLI Surface

```
python3 CryptoPriceTracker.py history [--days 90] [--date YYYY-MM-DD] [--play]
```

The command:

1. Loads holdings from the ledger (empty → message, exit 1).
2. Fetches `marketdata.fetch_history(coin, days)` for every coin in the ledger,
   skipping failures with a notice, building `price_by_coin_date` and the sorted
   `dates` grid.
3. If no usable history → message, exit 1.
4. Reconstructs the series; appends today's snapshot to `snapshots.jsonl`.
5. Best-effort: pools recent news (reusing the news config) and collects the set
   of window dates that have a matching headline; news failure → notice, skip.
6. Prints `format_chart`. If `--play`, prints `format_playback`. If `--date`,
   prints `format_snapshot` for that date (or the nearest available day, with a
   notice, if the exact date is not in the grid).

The default (no-arg) behavior and other subcommands are unchanged.

## Error Handling

- Empty ledger → clear message, exit 1.
- A coin whose history fetch fails → stderr notice; excluded from valuation.
- No usable history from any coin → clear message, exit 1.
- `--date` not in the date grid → use the nearest available date with a notice.
- News-fetch failure → non-fatal stderr notice; markers simply omitted.
- Live-price failure when building today's snapshot → skip the snapshot append
  with a notice (the reconstructed series and chart still print).

## Testing

`pytest`, no network (mock `fetch_history`, live prices, news). Coverage:

- `holdings_as_of`: a transaction dated after the cutoff is excluded; cutoff
  exactly on a transaction date includes it.
- `reconstruct_series`: known ledger + prices → hand-computed value and P/L per
  day; a coin missing a day's price is skipped for that day.
- `sparkline`: known values → expected glyph scaling; empty → ""; all-equal →
  uniform mid glyph.
- `hbar`: positive, negative, and zero; `max_abs <= 0` → empty.
- `make_snapshot` + `append_snapshot`/`load_snapshots`: JSONL round-trip; missing
  file → [].
- `format_chart` / `format_playback` (news `*` marker) / `format_snapshot`:
  expected substrings.
- CLI: `history` prints the chart; `--play` prints day lines; `--date` prints a
  snapshot (and nearest-day fallback); empty-ledger exit 1; a failing feed is
  skipped.
- Existing suite stays green.

## Out of Scope / Future

Hourly granularity and a real historical news archive would need different data
sources; daily reconstruction from CoinGecko + the ledger is the scope here.
