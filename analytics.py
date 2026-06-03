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
