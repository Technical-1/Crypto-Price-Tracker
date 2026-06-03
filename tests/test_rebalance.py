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
