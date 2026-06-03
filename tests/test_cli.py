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
