import json
import pytest
import staking


def test_load_config_valid(tmp_path):
    path = tmp_path / "staking.json"
    path.write_text(json.dumps({
        "ethereum": {"staked_qty": 2.0, "symbol": "ETH", "apy": 0.04},
        "stellar": {"staked_qty": 1000.0},
    }))
    cfg = staking.load_config(str(path))
    assert cfg["ethereum"] == {"staked_qty": 2.0, "symbol": "ETH", "apy": 0.04}
    assert cfg["stellar"] == {"staked_qty": 1000.0}


def test_load_config_missing_file_raises(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        staking.load_config(str(tmp_path / "nope.json"))


def test_load_config_malformed_raises(tmp_path):
    path = tmp_path / "staking.json"
    path.write_text("{not json")
    with pytest.raises(ValueError):
        staking.load_config(str(path))


def test_load_config_missing_staked_qty_raises(tmp_path):
    path = tmp_path / "staking.json"
    path.write_text(json.dumps({"ethereum": {"symbol": "ETH"}}))
    with pytest.raises(ValueError, match="staked_qty"):
        staking.load_config(str(path))


def test_load_config_nonpositive_staked_qty_raises(tmp_path):
    path = tmp_path / "staking.json"
    path.write_text(json.dumps({"ethereum": {"staked_qty": 0}}))
    with pytest.raises(ValueError, match="staked_qty"):
        staking.load_config(str(path))


def test_load_rewards_valid(tmp_path):
    path = tmp_path / "rewards.csv"
    path.write_text("date,coin,quantity\n2024-01-15,ethereum,0.01\n2024-02-15,ethereum,0.02\n")
    rewards = staking.load_rewards(str(path))
    assert rewards == [
        {"date": "2024-01-15", "coin": "ethereum", "quantity": 0.01},
        {"date": "2024-02-15", "coin": "ethereum", "quantity": 0.02},
    ]


def test_load_rewards_skips_invalid_rows(tmp_path, capsys):
    path = tmp_path / "rewards.csv"
    path.write_text("date,coin,quantity\n2024-01-15,ethereum,0.01\n2024-02-15,ethereum,notanumber\n")
    rewards = staking.load_rewards(str(path))
    assert rewards == [{"date": "2024-01-15", "coin": "ethereum", "quantity": 0.01}]
    assert "skipped" in capsys.readouterr().err


def test_load_rewards_missing_file_returns_empty(tmp_path):
    assert staking.load_rewards(str(tmp_path / "none.csv")) == []


import math


def test_effective_apys_prefers_api_then_manual_then_omits():
    config = {
        "ethereum": {"staked_qty": 2.0, "symbol": "ETH", "apy": 0.04},   # api present -> api
        "stellar": {"staked_qty": 1000.0, "symbol": "XLM", "apy": 0.03}, # api missing -> manual
        "eos": {"staked_qty": 5.0, "symbol": "EOS"},                     # neither -> omit
    }
    api_apys = {"ETH": 0.05}
    eff = staking.effective_apys(config, api_apys)
    assert eff["ethereum"] == (0.05, "api")
    assert eff["stellar"] == (0.03, "manual")
    assert "eos" not in eff


def test_projected_yield_annual_and_monthly():
    annual, monthly = staking.projected_yield(2.0, 0.04, days=365)
    assert math.isclose(annual, 0.08, rel_tol=1e-9)
    assert math.isclose(monthly, 0.08 / 12, rel_tol=1e-9)


def test_projected_yield_half_year_horizon():
    period, monthly = staking.projected_yield(2.0, 0.04, days=182.5)
    assert math.isclose(period, 0.04, rel_tol=1e-9)   # half of annual 0.08
    assert math.isclose(monthly, 0.08 / 12, rel_tol=1e-9)


def test_rewards_summary_sums_per_coin():
    rewards = [
        {"date": "2024-01-15", "coin": "ethereum", "quantity": 0.01},
        {"date": "2024-02-15", "coin": "ethereum", "quantity": 0.02},
        {"date": "2024-02-15", "coin": "stellar", "quantity": 100.0},
    ]
    summary = staking.rewards_summary(rewards)
    assert math.isclose(summary["ethereum"], 0.03, rel_tol=1e-9)
    assert summary["stellar"] == 100.0


def test_combined_pl_adds_rewards_value():
    assert staking.combined_pl(500.0, 120.0) == 620.0
