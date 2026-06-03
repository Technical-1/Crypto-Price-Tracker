import pytest
from unittest.mock import patch
import CryptoPriceTracker as cpt


def test_run_tax_command_prints_all_three_sections(tmp_path, capsys):
    import ledger
    ledger_path = tmp_path / "ledger.json"
    ledger.save_ledger(str(ledger_path), [
        ledger.Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        ledger.Transaction("2024-03-01", "bitcoin", "sell", 0.5, 200.0, 0.0),
    ])
    prices = {"bitcoin": {"usd": 300.0}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices):
        cpt.run_tax(ledger_path=str(ledger_path), taxconfig_path="taxconfig.json",
                    method="fifo", year=None)
    out = capsys.readouterr().out
    assert "Realized gains" in out
    assert "Unrealized P/L" in out
    assert "Estimated tax" in out


def test_import_missing_csv_exits_with_error(tmp_path, capsys):
    bad_path = str(tmp_path / "nonexistent.csv")
    with pytest.raises(SystemExit) as exc_info:
        cpt.cli(["import", bad_path])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "not found" in err.lower() or "CSV file not found" in err


def test_run_tax_year_filter_excludes_other_years(tmp_path, capsys):
    import ledger
    ledger_path = tmp_path / "ledger.json"
    ledger.save_ledger(str(ledger_path), [
        ledger.Transaction("2022-06-01", "bitcoin", "buy", 2.0, 20000.0, 0.0),
        ledger.Transaction("2023-07-15", "bitcoin", "sell", 0.5, 30000.0, 0.0),
        ledger.Transaction("2024-03-10", "bitcoin", "sell", 0.5, 40000.0, 0.0),
    ])
    prices = {"bitcoin": {"usd": 50000.0}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices):
        cpt.run_tax(ledger_path=str(ledger_path), taxconfig_path="taxconfig.json",
                    method="fifo", year=2023)
    out = capsys.readouterr().out

    # Isolate just the realized section (everything before the blank line after it)
    realized_section = out.split("\n\n")[0]
    assert "2023-07-15" in realized_section
    assert "2024-03-10" not in realized_section


def test_parser_defaults_to_no_command():
    parser = cpt.build_parser()
    args = parser.parse_args([])
    assert args.command is None


def test_parser_tax_method_and_year():
    parser = cpt.build_parser()
    args = parser.parse_args(["tax", "--method", "lifo", "--year", "2024"])
    assert args.command == "tax"
    assert args.method == "lifo"
    assert args.year == 2024
