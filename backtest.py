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
