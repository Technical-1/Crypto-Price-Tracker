# tests/test_tax.py
import json
import tax


def test_load_config_reads_valid_file(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({
        "jurisdiction": "US", "long_term_threshold_days": 365,
        "short_term_rate": 0.35,
        "long_term_brackets": [{"up_to": None, "rate": 0.15}],
    }))
    cfg = tax.load_tax_config(str(path))
    assert cfg["short_term_rate"] == 0.35


def test_load_config_missing_file_uses_defaults(tmp_path, capsys):
    cfg = tax.load_tax_config(str(tmp_path / "nope.json"))
    assert cfg == tax.DEFAULT_CONFIG
    assert "default tax config" in capsys.readouterr().err


def test_load_config_malformed_uses_defaults(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{ not json")
    cfg = tax.load_tax_config(str(path))
    assert cfg == tax.DEFAULT_CONFIG
    assert "default tax config" in capsys.readouterr().err
