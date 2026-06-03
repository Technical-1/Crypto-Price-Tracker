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


def test_parser_rebalance_options():
    parser = cpt.build_parser()
    args = parser.parse_args(["rebalance", "--strategy", "marketcap", "--days", "30"])
    assert args.command == "rebalance"
    assert args.strategy == "marketcap"
    assert args.days == 30


def test_parser_rebalance_defaults():
    parser = cpt.build_parser()
    args = parser.parse_args(["rebalance"])
    assert args.strategy == "equal"
    assert args.days == 90


def test_run_rebalance_prints_all_sections(tmp_path, capsys):
    import ledger
    ledger_path = tmp_path / "ledger.json"
    ledger.save_ledger(str(ledger_path), [
        ledger.Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        ledger.Transaction("2024-01-01", "ethereum", "buy", 10.0, 10.0, 0.0),
    ])
    prices = {"bitcoin": {"usd": 200.0}, "ethereum": {"usd": 20.0}}
    history = {
        "bitcoin": [("2024-01-01", 100.0), ("2024-02-01", 150.0), ("2024-03-01", 200.0)],
        "ethereum": [("2024-01-01", 10.0), ("2024-02-01", 15.0), ("2024-03-01", 20.0)],
    }
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices), \
         patch("CryptoPriceTracker.marketdata.fetch_history", side_effect=lambda c, days=90: history[c]):
        cpt.run_rebalance(ledger_path=str(ledger_path), strategy="equal", days=90)
    out = capsys.readouterr().out
    assert "Current allocation" in out
    assert "Risk (volatility)" in out
    assert "Correlation matrix" in out
    assert "Rebalancing trades" in out
    assert "Backtest" in out


def test_run_rebalance_empty_ledger_exits(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cpt.run_rebalance(ledger_path=str(tmp_path / "none.json"), strategy="equal", days=90)
    assert exc.value.code == 1


def test_parser_staking_defaults():
    parser = cpt.build_parser()
    args = parser.parse_args(["staking"])
    assert args.command == "staking"
    assert args.days == 365


def test_parser_staking_days():
    parser = cpt.build_parser()
    args = parser.parse_args(["staking", "--days", "30"])
    assert args.days == 30


def test_run_staking_prints_all_sections(tmp_path, capsys):
    import json
    import ledger
    ledger_path = tmp_path / "ledger.json"
    ledger.save_ledger(str(ledger_path), [
        ledger.Transaction("2024-01-01", "ethereum", "buy", 2.0, 100.0, 0.0),
    ])
    staking_path = tmp_path / "staking.json"
    staking_path.write_text(json.dumps({"ethereum": {"staked_qty": 2.0, "symbol": "ETH", "apy": 0.04}}))
    rewards_path = tmp_path / "rewards.csv"
    rewards_path.write_text("date,coin,quantity\n2024-02-01,ethereum,0.05\n")
    prices = {"ethereum": {"usd": 200.0}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices), \
         patch("CryptoPriceTracker.staking_api.fetch_apys", return_value={"ETH": 0.06}):
        cpt.run_staking(ledger_path=str(ledger_path), staking_path=str(staking_path),
                        rewards_path=str(rewards_path), days=365)
    out = capsys.readouterr().out
    assert "Staking yield" in out
    assert "Realized staking rewards" in out
    assert "Staked vs not staked" in out
    assert "Combined profit/loss" in out


def test_run_staking_falls_back_to_manual_on_api_error(tmp_path, capsys):
    import json
    import requests
    import ledger
    ledger.save_ledger(str(tmp_path / "ledger.json"), [
        ledger.Transaction("2024-01-01", "ethereum", "buy", 2.0, 100.0, 0.0)])
    staking_path = tmp_path / "staking.json"
    staking_path.write_text(json.dumps({"ethereum": {"staked_qty": 2.0, "symbol": "ETH", "apy": 0.04}}))
    prices = {"ethereum": {"usd": 200.0}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices), \
         patch("CryptoPriceTracker.staking_api.fetch_apys",
               side_effect=requests.ConnectionError("down")):
        cpt.run_staking(ledger_path=str(tmp_path / "ledger.json"),
                        staking_path=str(staking_path),
                        rewards_path=str(tmp_path / "none.csv"), days=365)
    captured = capsys.readouterr()
    assert "4.0" in captured.out          # manual 0.04 APY used
    assert "APY" in captured.err or "manual" in captured.err.lower() or "falling back" in captured.err.lower()


def test_run_staking_missing_config_exits(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cpt.run_staking(ledger_path=str(tmp_path / "ledger.json"),
                        staking_path=str(tmp_path / "none.json"),
                        rewards_path=str(tmp_path / "none.csv"), days=365)
    assert exc.value.code == 1


def test_run_staking_no_price_reward_prints_stderr_notice(tmp_path, capsys):
    """A reward coin absent from the price feed emits a stderr notice and values at 0."""
    import json
    import ledger
    ledger_path = tmp_path / "ledger.json"
    ledger.save_ledger(str(ledger_path), [])
    staking_path = tmp_path / "staking.json"
    staking_path.write_text(json.dumps({"ethereum": {"staked_qty": 1.0, "symbol": "ETH", "apy": 0.04}}))
    rewards_path = tmp_path / "rewards.csv"
    # "solana" appears in rewards but is absent from the mocked price feed
    rewards_path.write_text("date,coin,quantity\n2024-03-01,solana,2.5\n")
    # prices do NOT include "solana"
    prices = {"ethereum": {"usd": 200.0}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices), \
         patch("CryptoPriceTracker.staking_api.fetch_apys", return_value={"ETH": 0.04}):
        cpt.run_staking(ledger_path=str(ledger_path), staking_path=str(staking_path),
                        rewards_path=str(rewards_path), days=365)
    captured = capsys.readouterr()
    assert "solana" in captured.err
    assert "no live price" in captured.err or "reward value omitted" in captured.err


def test_run_staking_no_apy_prints_skipped_notice(tmp_path, capsys):
    """A coin with no API match and no manual APY produces a stderr skip notice
    and is absent from the yield table."""
    import json
    staking_path = tmp_path / "staking.json"
    # "solana" has a symbol but NO manual apy; API returns {} so no API APY either.
    staking_path.write_text(json.dumps({"solana": {"staked_qty": 5.0, "symbol": "SOL"}}))
    prices = {"solana": {"usd": 150.0}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices), \
         patch("CryptoPriceTracker.staking_api.fetch_apys", return_value={}):
        cpt.run_staking(ledger_path=str(tmp_path / "ledger.json"),
                        staking_path=str(staking_path),
                        rewards_path=str(tmp_path / "none.csv"), days=365)
    captured = capsys.readouterr()
    # The coin must not appear in the yield table output.
    assert "solana" not in captured.out
    # stderr must contain a skip/no-APY notice for the coin.
    assert "solana" in captured.err
    assert "skipped" in captured.err or "no APY" in captured.err


# --- Task 5: news subcommand ---

def test_parser_news_defaults():
    parser = cpt.build_parser()
    args = parser.parse_args(["news"])
    assert args.command == "news"
    assert args.coin is None
    assert args.limit == 5


def test_parser_news_options():
    parser = cpt.build_parser()
    args = parser.parse_args(["news", "--coin", "bitcoin", "--limit", "3"])
    assert args.coin == "bitcoin"
    assert args.limit == 3


def test_run_news_prints_section_for_coin(tmp_path, capsys):
    items = [
        {"title": "Bitcoin surges to record", "link": "https://x.test/a",
         "published": "2024-10-02", "source": "S"},
        {"title": "Ethereum news", "link": "https://x.test/b",
         "published": "2024-10-02", "source": "S"},
    ]
    with patch("CryptoPriceTracker.news_source.fetch_rss", return_value=items):
        cpt.run_news(coin="bitcoin", limit=5, config_path=str(tmp_path / "none.json"))
    out = capsys.readouterr().out
    assert "bitcoin" in out
    assert "Bitcoin surges to record" in out
    assert "Ethereum news" not in out          # filtered out for bitcoin


def test_run_news_skips_failing_feed(tmp_path, capsys):
    import json
    import requests

    # Two feeds: one good, one bad.
    news_cfg = {
        "feeds": ["https://good.test/rss", "https://bad.test/rss"],
        "keywords": {"bitcoin": ["bitcoin"]},
    }
    cfg_path = tmp_path / "news.json"
    cfg_path.write_text(json.dumps(news_cfg))

    good_items = [
        {"title": "Bitcoin surges", "link": "https://x/a",
         "published": "2024-10-02", "source": "S"},
    ]

    def _fetch(url, timeout=10):
        if "bad" in url:
            raise requests.ConnectionError("down")
        return good_items

    with patch("CryptoPriceTracker.news_source.fetch_rss", side_effect=_fetch):
        cpt.run_news(coin="bitcoin", limit=5, config_path=str(cfg_path))

    captured = capsys.readouterr()
    # The bad feed should be mentioned in stderr with a skip notice.
    assert "bad.test" in captured.err or "skipped" in captured.err.lower()
    # The good feed's item must appear in stdout.
    assert "Bitcoin surges" in captured.out


def test_run_news_all_sources_fail_exits(tmp_path, capsys):
    import pytest
    import requests

    def _always_fail(url, timeout=10):
        raise requests.ConnectionError("down")

    with patch("CryptoPriceTracker.news_source.fetch_rss", side_effect=_always_fail):
        with pytest.raises(SystemExit) as exc:
            cpt.run_news(coin="bitcoin", limit=5,
                         config_path=str(tmp_path / "none.json"))

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no news" in err.lower() or "could not" in err.lower() or "no news could be fetched" in err.lower()


def test_run_news_no_coins_exits(tmp_path):
    import pytest
    # empty holdings (empty ledger) and no --coin -> exit 1
    with patch("CryptoPriceTracker.holdings_mod.load_holdings_or_default", return_value={}):
        with pytest.raises(SystemExit) as exc:
            cpt.run_news(coin=None, limit=5, config_path=str(tmp_path / "none.json"),
                         ledger_path=str(tmp_path / "none.json"))
    assert exc.value.code == 1


# --- Task 6: history subcommand ---

def test_parser_history_defaults():
    parser = cpt.build_parser()
    args = parser.parse_args(["history"])
    assert args.command == "history"
    assert args.days == 90
    assert args.date is None
    assert args.play is False


def test_parser_history_options():
    parser = cpt.build_parser()
    args = parser.parse_args(["history", "--days", "30", "--date", "2024-01-02", "--play"])
    assert args.days == 30
    assert args.date == "2024-01-02"
    assert args.play is True


def _history_fixture(tmp_path):
    import ledger
    ledger_path = tmp_path / "ledger.json"
    ledger.save_ledger(str(ledger_path), [
        ledger.Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
    ])
    hist = {"bitcoin": [("2024-01-01", 100.0), ("2024-01-02", 150.0), ("2024-01-03", 120.0)]}
    return str(ledger_path), hist


def test_run_history_prints_chart(tmp_path, capsys):
    ledger_path, hist = _history_fixture(tmp_path)
    prices = {"bitcoin": {"usd": 120.0}}
    snap_path = tmp_path / "snapshots.jsonl"
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices), \
         patch("CryptoPriceTracker.marketdata.fetch_history", side_effect=lambda c, days=90: hist[c]), \
         patch("CryptoPriceTracker.news_source.fetch_rss", return_value=[]):
        cpt.run_history(ledger_path=ledger_path, snapshots_path=str(snap_path),
                        days=90, date=None, play=False)
    out = capsys.readouterr().out
    assert "Portfolio history" in out
    # a snapshot was appended
    import history
    assert len(history.load_snapshots(str(snap_path))) == 1


def test_run_history_play_and_date(tmp_path, capsys):
    ledger_path, hist = _history_fixture(tmp_path)
    prices = {"bitcoin": {"usd": 120.0}}
    with patch("CryptoPriceTracker.fetch_prices", return_value=prices), \
         patch("CryptoPriceTracker.marketdata.fetch_history", side_effect=lambda c, days=90: hist[c]), \
         patch("CryptoPriceTracker.news_source.fetch_rss", return_value=[]):
        cpt.run_history(ledger_path=ledger_path, snapshots_path=str(tmp_path / "s.jsonl"),
                        days=90, date="2024-01-02", play=True)
    out = capsys.readouterr().out
    assert "Playback" in out
    assert "Snapshot 2024-01-02" in out


def test_run_history_empty_ledger_exits(tmp_path):
    import pytest
    with patch("CryptoPriceTracker.holdings_mod.load_holdings_or_default", return_value={}):
        with pytest.raises(SystemExit) as exc:
            cpt.run_history(ledger_path=str(tmp_path / "none.json"),
                            snapshots_path=str(tmp_path / "s.jsonl"),
                            days=90, date=None, play=False)
    assert exc.value.code == 1


def test_run_news_cryptopanic_currencies_from_keywords(tmp_path, capsys):
    """fetch_cryptopanic is called with uppercased keyword-derived currencies (e.g.
    'BTC', 'BITCOIN'), NOT the raw CoinGecko id ('BITCOIN' only via c.upper())."""
    import json
    from unittest.mock import Mock

    news_cfg = {
        "feeds": [],
        "cryptopanic_token": "tok",
        "keywords": {"bitcoin": ["bitcoin", "btc"]},
    }
    news_json = tmp_path / "news.json"
    news_json.write_text(json.dumps(news_cfg))

    cp_item = {
        "title": "Bitcoin hits new high",
        "link": "https://cryptopanic.test/1",
        "published": "2024-10-02",
        "source": "CryptoPanic",
    }
    mock_fetch_cp = Mock(return_value=[cp_item])

    with patch("CryptoPriceTracker.news_source.fetch_cryptopanic", mock_fetch_cp), \
         patch("CryptoPriceTracker.news_source.fetch_rss", return_value=[]):
        cpt.run_news(coin="bitcoin", limit=5, config_path=str(news_json))

    mock_fetch_cp.assert_called_once()
    called_currencies = mock_fetch_cp.call_args[0][1]
    assert "BTC" in called_currencies
    assert "BITCOIN" in called_currencies
