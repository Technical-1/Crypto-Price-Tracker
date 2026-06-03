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
