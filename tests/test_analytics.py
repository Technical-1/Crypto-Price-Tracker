import math
import analytics


def test_daily_returns_simple_series():
    # prices 100 -> 110 -> 99: returns 0.1 then -0.1
    rets = analytics.daily_returns([100.0, 110.0, 99.0])
    assert len(rets) == 2
    assert math.isclose(rets[0], 0.1, rel_tol=1e-9)
    assert math.isclose(rets[1], -0.1, rel_tol=1e-9)


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
