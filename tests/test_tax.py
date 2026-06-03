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


from costbasis import Disposal


def _d(term, gain, sell_date="2024-05-01"):
    return Disposal("bitcoin", sell_date, 1.0, 0.0, 0.0, gain, 10, term)


def test_summarize_splits_short_and_long():
    disposals = [_d("short", 100.0), _d("long", 200.0), _d("short", -50.0)]
    short, long = tax.summarize(disposals)
    assert short == 50.0
    assert long == 200.0


def test_summarize_filters_by_year():
    disposals = [_d("short", 100.0, "2023-05-01"), _d("short", 40.0, "2024-05-01")]
    short, long = tax.summarize(disposals, year=2024)
    assert short == 40.0
    assert long == 0.0


def test_estimate_long_term_tax_progressive_brackets():
    brackets = [{"up_to": 100.0, "rate": 0.0}, {"up_to": 200.0, "rate": 0.15},
                {"up_to": None, "rate": 0.20}]
    # 250 gain: 0 on first 100, 15% on next 100 (15), 20% on last 50 (10) = 25
    assert tax.estimate_long_term_tax(250.0, brackets) == 25.0


def test_estimate_tax_floors_losses_at_zero():
    cfg = {"short_term_rate": 0.35,
           "long_term_brackets": [{"up_to": None, "rate": 0.15}]}
    st, lt = tax.estimate_tax(-100.0, -50.0, cfg)
    assert st == 0.0
    assert lt == 0.0
