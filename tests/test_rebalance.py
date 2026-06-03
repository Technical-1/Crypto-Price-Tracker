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
