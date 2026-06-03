# Portfolio Optimization & Rebalancing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CLI `rebalance` command that shows current allocation, per-coin and portfolio risk (volatility + correlation), suggests target allocations (equal / market-cap / custom) with buy/sell trades, and runs a simple buy-and-hold backtest.

**Architecture:** New stdlib-only modules around the existing code, reusing `holdings.py` (ledger-derived holdings) and the resilient CoinGecko fetch ethos. `analytics.py` (risk math, pure), `rebalance.py` (targets + trades), `backtest.py` (what-if), `marketdata.py` (historical + market-cap fetch), `rebalance_report.py` (formatting). `CryptoPriceTracker.py` gains a `rebalance` subcommand.

**Tech Stack:** Python 3, stdlib (`statistics`, `math`, `json`, `argparse`), `requests` (existing), `pytest`.

---

## File Structure

- `analytics.py` — `daily_returns`, `volatility`, `annualize`, `correlation`, `correlation_matrix`, `portfolio_volatility`. Pure functions, no network.
- `rebalance.py` — `target_weights`, `load_targets`, `compute_trades`.
- `backtest.py` — `buy_and_hold_return`.
- `marketdata.py` — `fetch_history`, `fetch_market_caps` (network; mirror `fetch_prices` style).
- `rebalance_report.py` — `format_allocation`, `format_risk`, `format_correlation`, `format_trades`, `format_backtest` (return strings).
- `CryptoPriceTracker.py` — add `run_rebalance(...)`, extend `build_parser`/`cli` with the `rebalance` subcommand.
- `targets.sample.json` — committed sample custom-target file.
- Tests: `tests/test_analytics.py`, `tests/test_rebalance.py`, `tests/test_backtest.py`, `tests/test_marketdata.py`, `tests/test_rebalance_report.py`, and additions to `tests/test_cli.py`.

Shared shapes (use exactly these): holdings dict `{coin: {"total", "cost"}}`; prices `{coin: {"usd": float}}`; history = `list[(date_str, float)]`; `current_values` = `{coin: usd_value}`; `target_weights`/weights = `{coin: fraction}` summing to 1.0; a trade = dict `{"coin", "action", "delta_usd", "coin_amount", "target_pct"}`.

---

## Task 1: analytics — daily returns & volatility

**Files:**
- Create: `analytics.py`
- Test: `tests/test_analytics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_analytics.py
import math
import analytics


def test_daily_returns_simple_series():
    # prices 100 -> 110 -> 99: returns 0.1 then -0.1
    rets = analytics.daily_returns([100.0, 110.0, 99.0])
    assert rets == [0.1, -0.1]


def test_daily_returns_too_short_is_empty():
    assert analytics.daily_returns([100.0]) == []
    assert analytics.daily_returns([]) == []


def test_volatility_is_population_stdev():
    # returns [0.1, -0.1]: mean 0, pstdev = 0.1
    assert math.isclose(analytics.volatility([0.1, -0.1]), 0.1, rel_tol=1e-9)


def test_volatility_empty_is_zero():
    assert analytics.volatility([]) == 0.0
    assert analytics.volatility([0.05]) == 0.0


def test_annualize_scales_by_sqrt_365():
    assert math.isclose(analytics.annualize(0.1), 0.1 * math.sqrt(365), rel_tol=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_analytics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analytics'`

- [ ] **Step 3: Write minimal implementation**

```python
# analytics.py
import math
import statistics


def daily_returns(prices):
    """Simple daily returns from a price list: p[i]/p[i-1] - 1.
    Fewer than 2 prices -> []."""
    if len(prices) < 2:
        return []
    return [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]


def volatility(returns):
    """Population stdev of a returns list (daily volatility). Empty or singleton
    -> 0.0."""
    if len(returns) < 2:
        return 0.0
    return statistics.pstdev(returns)


def annualize(daily_vol):
    """Scale a daily volatility to annual (sqrt of 365 trading days)."""
    return daily_vol * math.sqrt(365)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_analytics.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat: add daily returns and volatility analytics"
```

---

## Task 2: analytics — correlation & matrix

**Files:**
- Modify: `analytics.py`
- Test: `tests/test_analytics.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_analytics.py

def test_correlation_perfectly_correlated():
    a = [0.1, 0.2, 0.3, 0.1]
    b = [0.2, 0.4, 0.6, 0.2]  # exactly 2x a
    assert math.isclose(analytics.correlation(a, b), 1.0, rel_tol=1e-9)


def test_correlation_anti_correlated():
    a = [0.1, 0.2, 0.3, 0.1]
    b = [-0.1, -0.2, -0.3, -0.1]
    assert math.isclose(analytics.correlation(a, b), -1.0, rel_tol=1e-9)


def test_correlation_constant_series_is_zero():
    a = [0.1, 0.2, 0.3]
    b = [0.5, 0.5, 0.5]  # zero variance
    assert analytics.correlation(a, b) == 0.0


def test_correlation_matrix_diagonal_is_one():
    returns_by_coin = {
        "bitcoin": [0.1, 0.2, 0.3, 0.1],
        "ethereum": [0.2, 0.4, 0.6, 0.2],
    }
    m = analytics.correlation_matrix(returns_by_coin)
    assert m[("bitcoin", "bitcoin")] == 1.0
    assert m[("ethereum", "ethereum")] == 1.0
    assert math.isclose(m[("bitcoin", "ethereum")], 1.0, rel_tol=1e-9)
    assert math.isclose(m[("ethereum", "bitcoin")], 1.0, rel_tol=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_analytics.py -k correlation -v`
Expected: FAIL with `AttributeError: module 'analytics' has no attribute 'correlation'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to analytics.py

def correlation(returns_a, returns_b):
    """Pearson correlation over the overlapping prefix of two return series.
    A constant (zero-variance) series yields 0.0 (correlation undefined)."""
    n = min(len(returns_a), len(returns_b))
    if n < 2:
        return 0.0
    a = returns_a[:n]
    b = returns_b[:n]
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((x - mean_b) ** 2 for x in b)
    if var_a == 0 or var_b == 0:
        return 0.0
    return cov / math.sqrt(var_a * var_b)


def correlation_matrix(returns_by_coin):
    """All-pairs Pearson correlation. Diagonal is 1.0. Returns {(a, b): corr}."""
    coins = list(returns_by_coin)
    matrix = {}
    for a in coins:
        for b in coins:
            if a == b:
                matrix[(a, b)] = 1.0
            else:
                matrix[(a, b)] = correlation(returns_by_coin[a], returns_by_coin[b])
    return matrix
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_analytics.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat: add correlation and correlation matrix"
```

---

## Task 3: analytics — portfolio volatility

**Files:**
- Modify: `analytics.py`
- Test: `tests/test_analytics.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_analytics.py

def test_portfolio_volatility_two_assets():
    # weights 0.5/0.5; vols 0.2/0.4; correlation 0.0
    # var = .5^2*.2^2 + .5^2*.4^2 + 2*.5*.5*.2*.4*0 = .01 + .04 = .05
    # vol = sqrt(.05)
    weights = {"a": 0.5, "b": 0.5}
    vols = {"a": 0.2, "b": 0.4}
    corr = {("a", "a"): 1.0, ("b", "b"): 1.0, ("a", "b"): 0.0, ("b", "a"): 0.0}
    result = analytics.portfolio_volatility(weights, vols, corr)
    assert math.isclose(result, math.sqrt(0.05), rel_tol=1e-9)


def test_portfolio_volatility_perfectly_correlated_is_weighted_sum():
    # corr 1.0 everywhere -> portfolio vol = w_a*vol_a + w_b*vol_b
    weights = {"a": 0.5, "b": 0.5}
    vols = {"a": 0.2, "b": 0.4}
    corr = {("a", "a"): 1.0, ("b", "b"): 1.0, ("a", "b"): 1.0, ("b", "a"): 1.0}
    result = analytics.portfolio_volatility(weights, vols, corr)
    assert math.isclose(result, 0.3, rel_tol=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_analytics.py -k portfolio -v`
Expected: FAIL with `AttributeError: module 'analytics' has no attribute 'portfolio_volatility'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to analytics.py

def portfolio_volatility(weights, vols, corr):
    """sqrt(sum_i sum_j w_i w_j sigma_i sigma_j rho_ij) over the coins in weights.
    Missing correlation pairs default to 0.0 (treated as uncorrelated)."""
    coins = list(weights)
    total = 0.0
    for a in coins:
        for b in coins:
            rho = corr.get((a, b), 1.0 if a == b else 0.0)
            total += weights[a] * weights[b] * vols.get(a, 0.0) * vols.get(b, 0.0) * rho
    return math.sqrt(total) if total > 0 else 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_analytics.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat: add portfolio volatility from weights and correlations"
```

---

## Task 4: rebalance — target weights

**Files:**
- Create: `rebalance.py`
- Test: `tests/test_rebalance.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rebalance.py
import math
import pytest
import rebalance


def test_equal_weights():
    w = rebalance.target_weights("equal", ["bitcoin", "ethereum", "eos"])
    assert all(math.isclose(v, 1 / 3, rel_tol=1e-9) for v in w.values())
    assert math.isclose(sum(w.values()), 1.0, rel_tol=1e-9)


def test_marketcap_weights_normalize():
    caps = {"bitcoin": 600.0, "ethereum": 300.0, "eos": 100.0}
    w = rebalance.target_weights("marketcap", list(caps), market_caps=caps)
    assert math.isclose(w["bitcoin"], 0.6, rel_tol=1e-9)
    assert math.isclose(w["ethereum"], 0.3, rel_tol=1e-9)
    assert math.isclose(w["eos"], 0.1, rel_tol=1e-9)


def test_marketcap_skips_missing_cap_and_renormalizes():
    caps = {"bitcoin": 600.0, "ethereum": 400.0}  # eos missing
    w = rebalance.target_weights("marketcap", ["bitcoin", "ethereum", "eos"], market_caps=caps)
    assert "eos" not in w
    assert math.isclose(w["bitcoin"], 0.6, rel_tol=1e-9)
    assert math.isclose(w["ethereum"], 0.4, rel_tol=1e-9)


def test_custom_weights_passthrough():
    custom = {"bitcoin": 0.7, "ethereum": 0.3}
    w = rebalance.target_weights("custom", ["bitcoin", "ethereum"], custom=custom)
    assert w == custom


def test_unknown_strategy_raises():
    with pytest.raises(ValueError, match="strategy"):
        rebalance.target_weights("magic", ["bitcoin"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_rebalance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rebalance'`

- [ ] **Step 3: Write minimal implementation**

```python
# rebalance.py


def target_weights(strategy, coins, market_caps=None, custom=None):
    """Return {coin: weight} summing to 1.0 for the chosen strategy.
    - equal: 1/N over coins.
    - marketcap: proportional to market_caps; coins with missing/zero cap are
      dropped and the rest renormalized.
    - custom: the provided custom dict (assumed pre-validated to sum to ~1)."""
    if strategy == "equal":
        n = len(coins)
        return {c: 1.0 / n for c in coins}
    if strategy == "marketcap":
        caps = market_caps or {}
        usable = {c: caps[c] for c in coins if caps.get(c, 0) > 0}
        total = sum(usable.values())
        if total <= 0:
            raise ValueError("marketcap strategy: no usable market-cap data")
        return {c: cap / total for c, cap in usable.items()}
    if strategy == "custom":
        if not custom:
            raise ValueError("custom strategy requires target weights")
        return dict(custom)
    raise ValueError(f"unknown strategy {strategy!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_rebalance.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add rebalance.py tests/test_rebalance.py
git commit -m "feat: add target-weight strategies (equal, marketcap, custom)"
```

---

## Task 5: rebalance — load & validate custom targets

**Files:**
- Modify: `rebalance.py`
- Test: `tests/test_rebalance.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_rebalance.py
import json


def test_load_targets_valid(tmp_path):
    path = tmp_path / "targets.json"
    path.write_text(json.dumps({"bitcoin": 0.6, "ethereum": 0.4}))
    assert rebalance.load_targets(str(path)) == {"bitcoin": 0.6, "ethereum": 0.4}


def test_load_targets_missing_file_raises(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        rebalance.load_targets(str(tmp_path / "nope.json"))


def test_load_targets_bad_sum_raises(tmp_path):
    path = tmp_path / "targets.json"
    path.write_text(json.dumps({"bitcoin": 0.6, "ethereum": 0.6}))  # sums 1.2
    with pytest.raises(ValueError, match="sum"):
        rebalance.load_targets(str(path))


def test_load_targets_malformed_json_raises(tmp_path):
    path = tmp_path / "targets.json"
    path.write_text("{not json")
    with pytest.raises(ValueError):
        rebalance.load_targets(str(path))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_rebalance.py -k load_targets -v`
Expected: FAIL with `AttributeError: module 'rebalance' has no attribute 'load_targets'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to rebalance.py
import json


def load_targets(path):
    """Load {coin: fraction} custom targets from JSON. Raises ValueError if the
    file is missing, malformed, or the weights do not sum to ~1.0 (tol 1e-6)."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"targets file not found: {path}")
    except json.JSONDecodeError as err:
        raise ValueError(f"targets file is not valid JSON: {err}")
    if not isinstance(data, dict) or not data:
        raise ValueError("targets file must be a non-empty object of coin->fraction")
    total = sum(data.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"target weights must sum to 1.0, got {total}")
    return {c: float(w) for c, w in data.items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_rebalance.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add rebalance.py tests/test_rebalance.py
git commit -m "feat: load and validate custom target weights"
```

---

## Task 6: rebalance — compute trades

**Files:**
- Modify: `rebalance.py`
- Test: `tests/test_rebalance.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_rebalance.py

def test_compute_trades_rebalances_to_target():
    # total 1000; current 700/300; target 50/50 -> sell 200 of a, buy 200 of b
    current_values = {"a": 700.0, "b": 300.0}
    weights = {"a": 0.5, "b": 0.5}
    prices = {"a": {"usd": 10.0}, "b": {"usd": 5.0}}
    trades = {t["coin"]: t for t in rebalance.compute_trades(current_values, weights, prices)}
    assert math.isclose(trades["a"]["delta_usd"], -200.0, rel_tol=1e-9)
    assert trades["a"]["action"] == "sell"
    assert math.isclose(trades["a"]["coin_amount"], -20.0, rel_tol=1e-9)  # -200 / 10
    assert math.isclose(trades["b"]["delta_usd"], 200.0, rel_tol=1e-9)
    assert trades["b"]["action"] == "buy"
    assert math.isclose(trades["b"]["coin_amount"], 40.0, rel_tol=1e-9)   # 200 / 5


def test_compute_trades_full_sell_when_target_absent():
    # 'b' has no target -> weight 0 -> sell all of b
    current_values = {"a": 500.0, "b": 500.0}
    weights = {"a": 1.0}
    prices = {"a": {"usd": 10.0}, "b": {"usd": 5.0}}
    trades = {t["coin"]: t for t in rebalance.compute_trades(current_values, weights, prices)}
    assert trades["b"]["action"] == "sell"
    assert math.isclose(trades["b"]["delta_usd"], -500.0, rel_tol=1e-9)


def test_compute_trades_buy_from_zero():
    # 'b' held nothing but target wants 50% -> buy
    current_values = {"a": 1000.0}
    weights = {"a": 0.5, "b": 0.5}
    prices = {"a": {"usd": 10.0}, "b": {"usd": 5.0}}
    trades = {t["coin"]: t for t in rebalance.compute_trades(current_values, weights, prices)}
    assert trades["b"]["action"] == "buy"
    assert math.isclose(trades["b"]["delta_usd"], 500.0, rel_tol=1e-9)
    assert math.isclose(trades["b"]["coin_amount"], 100.0, rel_tol=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_rebalance.py -k compute_trades -v`
Expected: FAIL with `AttributeError: module 'rebalance' has no attribute 'compute_trades'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to rebalance.py

def compute_trades(current_values, target_weights, prices):
    """For every coin held or targeted, compute the trade to reach the target
    allocation, keeping total portfolio value constant.
    Returns a list of dicts: coin, action ('buy'/'sell'/'hold'), delta_usd,
    coin_amount, target_pct. Coins held but not targeted get weight 0 (full sell);
    coins targeted but unheld are bought from zero."""
    total = sum(current_values.values())
    coins = sorted(set(current_values) | set(target_weights))
    trades = []
    for coin in coins:
        weight = target_weights.get(coin, 0.0)
        target_value = weight * total
        current_value = current_values.get(coin, 0.0)
        delta_usd = target_value - current_value
        price = (prices.get(coin) or {}).get("usd")
        coin_amount = delta_usd / price if price else 0.0
        if delta_usd > 1e-9:
            action = "buy"
        elif delta_usd < -1e-9:
            action = "sell"
        else:
            action = "hold"
        trades.append({
            "coin": coin, "action": action, "delta_usd": delta_usd,
            "coin_amount": coin_amount, "target_pct": weight * 100,
        })
    return trades
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_rebalance.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add rebalance.py tests/test_rebalance.py
git commit -m "feat: compute rebalancing trades to reach target weights"
```

---

## Task 7: backtest — buy-and-hold return

**Files:**
- Create: `backtest.py`
- Test: `tests/test_backtest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backtest.py
import math
import backtest


def test_buy_and_hold_return_two_coins():
    # a: 100 -> 150 (+50%); b: 200 -> 200 (0%); weights 0.5/0.5
    history = {
        "a": [("2024-01-01", 100.0), ("2024-02-01", 120.0), ("2024-03-01", 150.0)],
        "b": [("2024-01-01", 200.0), ("2024-03-01", 200.0)],
    }
    weights = {"a": 0.5, "b": 0.5}
    # 0.5*0.5 + 0.5*0.0 = 0.25
    assert math.isclose(backtest.buy_and_hold_return(history, weights), 0.25, rel_tol=1e-9)


def test_buy_and_hold_skips_missing_history_and_renormalizes():
    # b has no history -> drop b, renormalize to a only -> a return only (+50%)
    history = {"a": [("2024-01-01", 100.0), ("2024-03-01", 150.0)]}
    weights = {"a": 0.5, "b": 0.5}
    assert math.isclose(backtest.buy_and_hold_return(history, weights), 0.5, rel_tol=1e-9)


def test_buy_and_hold_empty_returns_zero():
    assert backtest.buy_and_hold_return({}, {"a": 1.0}) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_backtest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backtest'`

- [ ] **Step 3: Write minimal implementation**

```python
# backtest.py


def buy_and_hold_return(history_by_coin, weights):
    """Fractional buy-and-hold return over the window for the given weights:
    sum_i w_i * (price_end_i / price_start_i - 1), using the first and last daily
    price per coin. Coins lacking usable history are dropped and the remaining
    weights renormalized. Returns 0.0 if no coin has usable history."""
    usable = {}
    for coin, weight in weights.items():
        series = history_by_coin.get(coin) or []
        if len(series) >= 2 and series[0][1] > 0:
            usable[coin] = weight
    total_weight = sum(usable.values())
    if total_weight <= 0:
        return 0.0
    result = 0.0
    for coin, weight in usable.items():
        series = history_by_coin[coin]
        start = series[0][1]
        end = series[-1][1]
        norm_weight = weight / total_weight
        result += norm_weight * (end / start - 1)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_backtest.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backtest.py tests/test_backtest.py
git commit -m "feat: add buy-and-hold backtest over the price window"
```

---

## Task 8: marketdata — historical & market-cap fetch

**Files:**
- Create: `marketdata.py`
- Test: `tests/test_marketdata.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_marketdata.py
from unittest.mock import Mock, patch
import marketdata


def test_fetch_history_reduces_to_daily_date_price():
    fake = Mock()
    fake.raise_for_status.return_value = None
    # CoinGecko market_chart: prices = [[ms_ts, price], ...]
    fake.json.return_value = {"prices": [
        [1704067200000, 100.0],  # 2024-01-01
        [1704153600000, 110.0],  # 2024-01-02
    ]}
    with patch("marketdata.requests.get", return_value=fake) as mock_get:
        series = marketdata.fetch_history("bitcoin", days=2, timeout=10)
    assert series == [("2024-01-01", 100.0), ("2024-01-02", 110.0)]
    assert mock_get.call_count == 1
    # the URL should reference the coin id and days
    called_url = mock_get.call_args[0][0]
    assert "bitcoin" in called_url and "days=2" in called_url


def test_fetch_market_caps_parses_usd_market_cap():
    fake = Mock()
    fake.raise_for_status.return_value = None
    fake.json.return_value = {
        "bitcoin": {"usd": 50000, "usd_market_cap": 1.0e12},
        "ethereum": {"usd": 3000, "usd_market_cap": 4.0e11},
    }
    with patch("marketdata.requests.get", return_value=fake):
        caps = marketdata.fetch_market_caps(["bitcoin", "ethereum"])
    assert caps == {"bitcoin": 1.0e12, "ethereum": 4.0e11}


def test_fetch_history_propagates_http_error():
    import requests
    fake = Mock()
    fake.raise_for_status.side_effect = requests.HTTPError("429")
    with patch("marketdata.requests.get", return_value=fake):
        import pytest
        with pytest.raises(requests.HTTPError):
            marketdata.fetch_history("bitcoin", days=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_marketdata.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'marketdata'`

- [ ] **Step 3: Write minimal implementation**

```python
# marketdata.py
from datetime import datetime, timezone

import requests

HISTORY_URL = (
    "https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
    "?vs_currency=usd&days={days}&interval=daily"
)
MARKETCAP_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids={ids}&vs_currencies=usd&include_market_cap=true"
)


def fetch_history(coin, days=90, timeout=10):
    """Fetch daily USD prices for one coin as a list of (YYYY-MM-DD, price).
    Raises requests.RequestException on network/HTTP failure."""
    url = HISTORY_URL.format(coin=coin, days=days)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    points = response.json().get("prices", [])
    series = []
    for ms_ts, price in points:
        day = datetime.fromtimestamp(ms_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        series.append((day, price))
    return series


def fetch_market_caps(ids, timeout=10):
    """Fetch USD market caps for the given coin ids as {coin: market_cap}.
    Raises requests.RequestException on network/HTTP failure."""
    url = MARKETCAP_URL.format(ids="%2C".join(ids))
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    caps = {}
    for coin, fields in data.items():
        cap = fields.get("usd_market_cap")
        if cap is not None:
            caps[coin] = cap
    return caps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_marketdata.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add marketdata.py tests/test_marketdata.py
git commit -m "feat: add historical price and market-cap fetching"
```

---

## Task 9: rebalance_report — formatting

**Files:**
- Create: `rebalance_report.py`
- Test: `tests/test_rebalance_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rebalance_report.py
import rebalance_report


def test_format_allocation_shows_pct():
    current_values = {"bitcoin": 750.0, "ethereum": 250.0}
    out = rebalance_report.format_allocation(current_values)
    assert "bitcoin" in out and "ethereum" in out
    assert "75.0" in out and "25.0" in out


def test_format_risk_shows_per_coin_and_portfolio():
    vols_daily = {"bitcoin": 0.05, "ethereum": 0.08}
    vols_annual = {"bitcoin": 0.05 * 19.1, "ethereum": 0.08 * 19.1}
    out = rebalance_report.format_risk(vols_daily, vols_annual, 0.06)
    assert "bitcoin" in out and "ethereum" in out
    assert "Portfolio" in out


def test_format_correlation_renders_matrix():
    coins = ["bitcoin", "ethereum"]
    corr = {("bitcoin", "bitcoin"): 1.0, ("ethereum", "ethereum"): 1.0,
            ("bitcoin", "ethereum"): 0.42, ("ethereum", "bitcoin"): 0.42}
    out = rebalance_report.format_correlation(coins, corr)
    assert "bitcoin" in out and "ethereum" in out
    assert "0.42" in out


def test_format_trades_shows_actions():
    trades = [
        {"coin": "bitcoin", "action": "sell", "delta_usd": -200.0, "coin_amount": -0.004, "target_pct": 50.0},
        {"coin": "ethereum", "action": "buy", "delta_usd": 200.0, "coin_amount": 0.07, "target_pct": 50.0},
    ]
    out = rebalance_report.format_trades(trades)
    assert "sell" in out and "buy" in out
    assert "bitcoin" in out and "ethereum" in out


def test_format_backtest_shows_both_returns():
    out = rebalance_report.format_backtest(90, 0.12, 0.18, "equal")
    assert "90" in out
    assert "12.0" in out and "18.0" in out
    assert "equal" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_rebalance_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rebalance_report'`

- [ ] **Step 3: Write minimal implementation**

```python
# rebalance_report.py


def format_allocation(current_values):
    """Current allocation table: coin, USD value, percent of portfolio."""
    total = sum(current_values.values())
    lines = ["Current allocation:",
             "      Coin          Value       %",
             "  ------------   ----------   ------"]
    for coin in sorted(current_values, key=lambda c: -current_values[c]):
        value = current_values[coin]
        pct = (value / total * 100) if total else 0.0
        lines.append("  %-12s   %10.2f   %5.1f" % (coin, value, pct))
    return "\n".join(lines)


def format_risk(vols_daily, vols_annual, portfolio_vol):
    """Per-coin daily/annualized volatility plus the portfolio volatility."""
    lines = ["Risk (volatility):",
             "      Coin         Daily %    Annual %",
             "  ------------   --------   ---------"]
    for coin in sorted(vols_daily):
        lines.append("  %-12s   %7.2f   %8.2f" % (
            coin, vols_daily[coin] * 100, vols_annual.get(coin, 0.0) * 100))
    lines.append("  Portfolio daily volatility: %.2f%%" % (portfolio_vol * 100))
    return "\n".join(lines)


def format_correlation(coins, corr):
    """Labeled correlation matrix among coins."""
    lines = ["Correlation matrix:"]
    header = "  %-12s" % "" + "".join("%10s" % c[:9] for c in coins)
    lines.append(header)
    for a in coins:
        row = "  %-12s" % a[:12] + "".join(
            "%10.2f" % corr.get((a, b), 0.0) for b in coins)
        lines.append(row)
    return "\n".join(lines)


def format_trades(trades):
    """Rebalancing trades: coin, action, USD delta, coin amount, target %."""
    lines = ["Rebalancing trades:",
             "      Coin        Action     Delta USD     Coin Amount    Target %",
             "  ------------   --------   -----------   -------------   --------"]
    for t in trades:
        lines.append("  %-12s   %-8s   %11.2f   %13.6f   %7.1f" % (
            t["coin"], t["action"], t["delta_usd"], t["coin_amount"], t["target_pct"]))
    return "\n".join(lines)


def format_backtest(window_days, current_return, target_return, strategy):
    """Window buy-and-hold return: current weights vs target strategy."""
    return "\n".join([
        "Backtest (last %d days, buy & hold):" % window_days,
        "  Current allocation return: %6.1f%%" % (current_return * 100),
        "  Target (%s) return:        %6.1f%%" % (strategy, target_return * 100),
    ])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_rebalance_report.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add rebalance_report.py tests/test_rebalance_report.py
git commit -m "feat: add rebalance report formatting"
```

---

## Task 10: CLI — `rebalance` subcommand

**Files:**
- Modify: `CryptoPriceTracker.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_cli.py
from unittest.mock import patch
import CryptoPriceTracker as cpt


def test_parser_rebalance_options():
    parser = cpt.build_parser()
    args = parser.parse_args(["rebalance", "--strategy", "marketcap", "--days", "30"])
    assert args.command == "rebalance"
    assert args.strategy == "marketcap"
    assert args.days == 30


def test_parser_rebalance_defaults():
    parser = cpt.build_parser()
    args = parser.parse_args(["rebalance"])
    assert args.strategy == "equal"
    assert args.days == 90


def test_run_rebalance_prints_all_sections(tmp_path, capsys):
    import ledger
    ledger_path = tmp_path / "ledger.json"
    ledger.save_ledger(str(ledger_path), [
        ledger.Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        ledger.Transaction("2024-01-01", "ethereum", "buy", 10.0, 10.0, 0.0),
    ])
    prices = {"bitcoin": {"usd": 200.0}, "ethereum": {"usd": 20.0}}
    history = {
        "bitcoin": [("2024-01-01", 100.0), ("2024-02-01", 150.0), ("2024-03-01", 200.0)],
        "ethereum": [("2024-01-01", 10.0), ("2024-02-01", 15.0), ("2024-03-01", 20.0)],
    }
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices), \
         patch("CryptoPriceTracker.marketdata.fetch_history", side_effect=lambda c, days=90: history[c]):
        cpt.run_rebalance(ledger_path=str(ledger_path), strategy="equal", days=90)
    out = capsys.readouterr().out
    assert "Current allocation" in out
    assert "Risk (volatility)" in out
    assert "Correlation matrix" in out
    assert "Rebalancing trades" in out
    assert "Backtest" in out


def test_run_rebalance_empty_ledger_exits(tmp_path):
    import pytest
    with pytest.raises(SystemExit) as exc:
        cpt.run_rebalance(ledger_path=str(tmp_path / "none.json"), strategy="equal", days=90)
    assert exc.value.code == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -k rebalance -v`
Expected: FAIL with `AttributeError: module 'CryptoPriceTracker' has no attribute 'run_rebalance'`

- [ ] **Step 3: Write minimal implementation**

Add imports near the other new imports in `CryptoPriceTracker.py`:

```python
import marketdata
import analytics
import rebalance as rebalance_mod
import backtest
import rebalance_report
```

Add a constant near `LEDGER_PATH`:

```python
TARGETS_PATH = "targets.json"
```

Add the `run_rebalance` function above the `build_parser` definition:

```python
def run_rebalance(ledger_path=LEDGER_PATH, targets_path=TARGETS_PATH,
                  strategy="equal", days=90):
    """Print allocation, risk, target trades, and a backtest for the portfolio."""
    held = holdings_mod.load_holdings_or_default(ledger_path, {})
    if not held:
        print("No holdings found. Use 'import FILE.csv' or 'add' first.",
              file=sys.stderr)
        sys.exit(1)

    try:
        prices = fetch_prices(API_URL)
    except requests.RequestException as err:
        print(f"Failed to fetch prices: {err}", file=sys.stderr)
        sys.exit(1)

    coins = [c for c in held if (prices.get(c) or {}).get("usd") is not None]
    current_values = {c: held[c]["total"] * prices[c]["usd"] for c in coins}
    print(rebalance_report.format_allocation(current_values))
    print()

    # Historical risk: fetch per-coin history, skip coins that fail/are too short.
    history = {}
    for coin in coins:
        try:
            series = marketdata.fetch_history(coin, days=days)
        except requests.RequestException as err:
            print(f"  (skipped {coin} history: {err})", file=sys.stderr)
            continue
        if len(series) >= 2:
            history[coin] = series
        else:
            print(f"  (skipped {coin}: insufficient history)", file=sys.stderr)

    returns_by_coin = {c: analytics.daily_returns([p for _, p in s])
                       for c, s in history.items()}
    vols_daily = {c: analytics.volatility(r) for c, r in returns_by_coin.items()}
    vols_annual = {c: analytics.annualize(v) for c, v in vols_daily.items()}

    risk_coins = list(history)
    if len(risk_coins) >= 2:
        corr = analytics.correlation_matrix(returns_by_coin)
        # Weight by value among the coins that actually have history, so the
        # portfolio-volatility weights sum to 1 even if some coins were skipped.
        risk_total = sum(current_values.get(c, 0.0) for c in risk_coins)
        risk_weights = {c: current_values.get(c, 0.0) / risk_total for c in risk_coins} \
            if risk_total else {}
        port_vol = analytics.portfolio_volatility(risk_weights, vols_daily, corr)
        print(rebalance_report.format_risk(vols_daily, vols_annual, port_vol))
        print()
        print(rebalance_report.format_correlation(risk_coins, corr))
        print()
    elif vols_daily:
        print(rebalance_report.format_risk(vols_daily, vols_annual, 0.0))
        print("  (correlation/portfolio volatility skipped: need >= 2 coins with history)")
        print()
    else:
        print("(risk analytics skipped: no usable history)", file=sys.stderr)

    # Target weights + trades.
    market_caps = None
    custom = None
    if strategy == "marketcap":
        try:
            market_caps = marketdata.fetch_market_caps(coins)
        except requests.RequestException as err:
            print(f"Failed to fetch market caps: {err}", file=sys.stderr)
            sys.exit(1)
    if strategy == "custom":
        try:
            custom = rebalance_mod.load_targets(targets_path)
        except ValueError as err:
            print(f"Custom targets error: {err}", file=sys.stderr)
            sys.exit(1)
    try:
        weights = rebalance_mod.target_weights(strategy, coins,
                                               market_caps=market_caps, custom=custom)
    except ValueError as err:
        print(f"Rebalance error: {err}", file=sys.stderr)
        sys.exit(1)

    trades = rebalance_mod.compute_trades(current_values, weights, prices)
    print(rebalance_report.format_trades(trades))
    print()

    # Backtest current vs target weights over the fetched window.
    total_value = sum(current_values.values())
    cur_weights = {c: current_values[c] / total_value for c in current_values} \
        if total_value else {}
    current_return = backtest.buy_and_hold_return(history, cur_weights)
    target_return = backtest.buy_and_hold_return(history, weights)
    print(rebalance_report.format_backtest(days, current_return, target_return, strategy))
```

Extend `build_parser` by adding (before `return parser`):

```python
    reb = sub.add_parser("rebalance", help="allocation, risk, target trades, and backtest")
    reb.add_argument("--strategy", choices=["equal", "marketcap", "custom"], default="equal")
    reb.add_argument("--days", type=int, default=90)
```

Extend `cli` dispatch by adding a branch (before the `else: main()`):

```python
    elif args.command == "rebalance":
        run_rebalance(strategy=args.strategy, days=args.days)
```

- [ ] **Step 4: Run test to verify it passes (new + full suite)**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: PASS (rebalance tests plus existing CLI tests)

Run: `python3 -m pytest -v`
Expected: PASS (entire suite)

- [ ] **Step 5: Commit**

```bash
git add CryptoPriceTracker.py tests/test_cli.py
git commit -m "feat: add rebalance CLI subcommand wiring allocation, risk, trades, backtest"
```

---

## Task 11: Sample targets, docs, full verification

**Files:**
- Create: `targets.sample.json`
- Modify: `.gitignore`, `README.md`

- [ ] **Step 1: Create the sample custom-targets file**

```json
{
  "bitcoin": 0.4,
  "ethereum": 0.3,
  "stellar": 0.2,
  "uniswap": 0.1
}
```

Save as `targets.sample.json`.

- [ ] **Step 2: Ignore the user's runtime targets file**

Add to `.gitignore` (append, don't clobber):

```
targets.json
```

- [ ] **Step 3: Run the full suite and lint**

Run: `python3 -m pytest -v`
Expected: PASS (all)

Run: `python3 -m pyflakes CryptoPriceTracker.py analytics.py rebalance.py backtest.py marketdata.py rebalance_report.py`
Expected: clean (no output)

- [ ] **Step 4: Update the README**

Add a "Portfolio Rebalancing" section under the tax section documenting:
- the `rebalance [--strategy equal|marketcap|custom] [--days 90]` command and its five output sections (allocation, risk, correlation, trades, backtest);
- that `custom` reads `targets.json` (copy `targets.sample.json`), weights must sum to 1.0;
- that volatility is the stdev of daily returns (shown daily and annualized), and risk needs >= 2 coins with history;
- that the backtest is a simple buy-and-hold comparison over the chosen window.

Update the Project Structure tree to list `analytics.py`, `rebalance.py`, `backtest.py`, `marketdata.py`, `rebalance_report.py`, and `targets.sample.json`.

- [ ] **Step 5: Commit**

```bash
git add targets.sample.json .gitignore README.md
git commit -m "docs: document rebalancing; add sample targets and ignore runtime targets"
```

---

## Verification Checklist (run before opening the PR)

- [ ] `python3 -m pytest -v` — all green (existing + new).
- [ ] `python3 -m pyflakes *.py` — clean.
- [ ] `python3 CryptoPriceTracker.py` — still prints the live price table.
- [ ] `python3 CryptoPriceTracker.py rebalance` (with a ledger present) — prints all five sections.
- [ ] Spec coverage: current allocation ✔ (T9/T10), volatility ✔ (T1), correlation ✔ (T2), portfolio volatility ✔ (T3), target strategies equal/marketcap/custom ✔ (T4/T5), trades ✔ (T6), backtest ✔ (T7), historical & market-cap fetch ✔ (T8), graceful skips ✔ (T10), CLI ✔ (T10), docs/sample ✔ (T11).
