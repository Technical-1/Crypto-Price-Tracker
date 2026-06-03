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
