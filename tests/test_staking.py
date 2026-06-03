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
