import json


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
