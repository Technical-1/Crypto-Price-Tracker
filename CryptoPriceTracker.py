import argparse
import sys

import requests

import ledger as ledger_mod
import holdings as holdings_mod
import costbasis
import tax as tax_mod
import report
import marketdata
import analytics
import rebalance as rebalance_mod
import backtest
import rebalance_report
import staking as staking_mod
import staking_api
import staking_report

LEDGER_PATH = "ledger.json"
TAXCONFIG_PATH = "taxconfig.json"
TARGETS_PATH = "targets.json"
STAKING_PATH = "staking.json"
REWARDS_PATH = "rewards.csv"

API_URL = (
    "https://api.coingecko.com/api/v3/simple/price?"
    "ids=bitcoin%2Cethereum%2C1inch%2Cmirror-protocol%2Cthe-graph%2C"
    "decentraland%2Cenjincoin%2Cmaker%2Crepublic-protocol%2Cbarnbridge%2C"
    "origin-protocol%2Cclover-finance%2Cstellar%2Cuniswap%2Ceos"
    "&vs_currencies=usd&include_24hr_change=true"
)

originalHoldings = {"ethereum":          {"total": 1, "cost": 200},
                    "bitcoin":           {"total": 1, "cost": 200},
                    "1inch":             {"total": 1, "cost": 20},
                    "mirror-protocol":   {"total": 1, "cost": 20},
                    "the-graph":         {"total": 1, "cost": 20},
                    "decentraland":      {"total": 1, "cost": 20},
                    "enjincoin":         {"total": 1, "cost": 20},
                    "maker":             {"total": 1, "cost": 20},
                    "republic-protocol": {"total": 1, "cost": 20},
                    "barnbridge":        {"total": 1, "cost": 20},
                    "origin-protocol":   {"total": 1, "cost": 20},
                    "clover-finance":    {"total": 1, "cost": 20},
                    "stellar":           {"total": 1, "cost": 20},
                    "uniswap":           {"total": 1, "cost": 20},
                    "eos":               {"total": 1, "cost": 20}}


def fetch_prices(url, timeout=10):
    """Fetch current prices from CoinGecko. Raises requests.RequestException
    (incl. HTTPError from raise_for_status) on any network or HTTP failure."""
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def compute_profit(holding, price):
    """Return total profit for a holding at the given USD price, or None when
    the holding total is non-positive (avoids divide-by-zero on user input)."""
    total = holding['total']
    if total <= 0:
        return None
    avgCost = holding['cost'] / total
    return (price - avgCost) * total


def main(holdings=None, url=API_URL):
    if holdings is None:
        holdings = holdings_mod.load_holdings_or_default(LEDGER_PATH, originalHoldings)

    try:
        priceData = fetch_prices(url)
    except requests.RequestException as err:
        print(f"Failed to fetch prices from CoinGecko: {err}", file=sys.stderr)
        sys.exit(1)

    print("        Coin              Profit      Cost     24hr %")
    print("---------------------   ----------   ------   ---------")

    for key, value in holdings.items():
        coin = priceData.get(key)
        if coin is None or coin.get('usd') is None:
            print(f"  (skipped {key}: no price data returned)", file=sys.stderr)
            continue

        profit = compute_profit(value, coin['usd'])
        if profit is None:
            print(f"  (skipped {key}: invalid holding total <= 0)", file=sys.stderr)
            continue

        # A coin may report a price but omit 24h change; show the row anyway,
        # treating the missing change as 0.0% rather than skipping it.
        change = coin.get('usd_24h_change', 0.0)
        print("%20s     %8.2f     %8.2f      %5.2f" % (
            key, profit, value['cost'], change))


def run_tax(ledger_path=LEDGER_PATH, taxconfig_path=TAXCONFIG_PATH,
            method="fifo", year=None):
    """Print realized gains, unrealized P/L (live prices), and estimated tax."""
    txns = ledger_mod.load_ledger(ledger_path)
    if not txns:
        print("No transactions found. Use 'import FILE.csv' or 'add' first.",
              file=sys.stderr)
        sys.exit(1)

    config = tax_mod.load_tax_config(taxconfig_path)
    disposals, _ = costbasis.process_ledger(
        txns, method=method, long_term_threshold=config["long_term_threshold_days"])

    realized_for_report = disposals if year is None else [d for d in disposals if d.sell_date[:4] == str(year)]
    print(report.format_realized(realized_for_report))
    print()

    held = holdings_mod.derive_holdings(txns, method=method)
    try:
        prices = fetch_prices(API_URL)
        print(report.format_unrealized(held, prices))
    except requests.RequestException as err:
        print(f"(unrealized P/L unavailable: {err})", file=sys.stderr)
    print()

    short_gain, long_gain = tax_mod.summarize(disposals, year=year)
    short_tax, long_tax = tax_mod.estimate_tax(short_gain, long_gain, config)
    print(report.format_tax(short_gain, long_gain, short_tax, long_tax, config))


def run_rebalance(ledger_path=LEDGER_PATH, targets_path=TARGETS_PATH,
                  strategy="equal", days=90):
    """Print allocation, risk, target trades, and a backtest for the portfolio."""
    held = holdings_mod.load_holdings_or_default(ledger_path, {})
    if not held:
        print("No holdings found. Use 'import FILE.csv' or 'add' first.",
              file=sys.stderr)
        sys.exit(1)

    try:
        prices = fetch_prices(API_URL)
    except requests.RequestException as err:
        print(f"Failed to fetch prices: {err}", file=sys.stderr)
        sys.exit(1)

    coins = [c for c in held if (prices.get(c) or {}).get("usd") is not None]
    current_values = {c: held[c]["total"] * prices[c]["usd"] for c in coins}
    print(rebalance_report.format_allocation(current_values))
    print()

    # Historical risk: fetch per-coin history, skip coins that fail/are too short.
    history = {}
    for coin in coins:
        try:
            series = marketdata.fetch_history(coin, days=days)
        except requests.RequestException as err:
            print(f"  (skipped {coin} history: {err})", file=sys.stderr)
            continue
        if len(series) >= 2:
            history[coin] = series
        else:
            print(f"  (skipped {coin}: insufficient history)", file=sys.stderr)

    returns_by_coin = {c: analytics.daily_returns([p for _, p in s])
                       for c, s in history.items()}
    vols_daily = {c: analytics.volatility(r) for c, r in returns_by_coin.items()}
    vols_annual = {c: analytics.annualize(v) for c, v in vols_daily.items()}

    risk_coins = list(history)
    if len(risk_coins) >= 2:
        corr = analytics.correlation_matrix(returns_by_coin)
        # Weight by value among the coins that actually have history, so the
        # portfolio-volatility weights sum to 1 even if some coins were skipped.
        risk_total = sum(current_values.get(c, 0.0) for c in risk_coins)
        risk_weights = {c: current_values.get(c, 0.0) / risk_total for c in risk_coins} \
            if risk_total else {}
        port_vol = analytics.portfolio_volatility(risk_weights, vols_daily, corr)
        print(rebalance_report.format_risk(vols_daily, vols_annual, port_vol))
        print()
        print(rebalance_report.format_correlation(risk_coins, corr))
        print()
    elif vols_daily:
        print(rebalance_report.format_risk(vols_daily, vols_annual))
        print("  (correlation/portfolio volatility skipped: need >= 2 coins with history)")
        print()
    else:
        print("(risk analytics skipped: no usable history)", file=sys.stderr)

    # Target weights + trades.
    market_caps = None
    custom = None
    if strategy == "marketcap":
        try:
            market_caps = marketdata.fetch_market_caps(coins)
        except requests.RequestException as err:
            print(f"Failed to fetch market caps: {err}", file=sys.stderr)
            sys.exit(1)
    if strategy == "custom":
        try:
            custom = rebalance_mod.load_targets(targets_path)
        except ValueError as err:
            print(f"Custom targets error: {err}", file=sys.stderr)
            sys.exit(1)
    try:
        weights = rebalance_mod.target_weights(strategy, coins,
                                               market_caps=market_caps, custom=custom)
    except ValueError as err:
        print(f"Rebalance error: {err}", file=sys.stderr)
        sys.exit(1)

    trades = rebalance_mod.compute_trades(current_values, weights, prices)
    for t in trades:
        if abs(t["delta_usd"]) > 1e-6 and t["coin_amount"] == 0:
            print(f"  (note: no live price for {t['coin']}; coin amount unavailable, "
                  f"USD delta {t['delta_usd']:.2f})", file=sys.stderr)
    print(rebalance_report.format_trades(trades))
    print()

    # Backtest current vs target weights over the fetched window.
    total_value = sum(current_values.values())
    cur_weights = {c: current_values[c] / total_value for c in current_values} \
        if total_value else {}
    current_return = backtest.buy_and_hold_return(history, cur_weights)
    target_return = backtest.buy_and_hold_return(history, weights)
    print(rebalance_report.format_backtest(days, current_return, target_return, strategy))


def run_staking(ledger_path=LEDGER_PATH, staking_path=STAKING_PATH,
                rewards_path=REWARDS_PATH, days=365):
    """Print staking APY/yield, realized rewards, staked-vs-not, and combined P/L."""
    try:
        config = staking_mod.load_config(staking_path)
    except ValueError as err:
        print(f"Staking config error: {err}", file=sys.stderr)
        sys.exit(1)

    try:
        prices = fetch_prices(API_URL)
    except requests.RequestException as err:
        print(f"Failed to fetch prices: {err}", file=sys.stderr)
        sys.exit(1)

    symbols = [e["symbol"] for e in config.values() if e.get("symbol")]
    api_apys = {}
    if symbols:
        try:
            api_apys = staking_api.fetch_apys(symbols)
        except requests.RequestException as err:
            print(f"  (staking APY API unavailable, falling back to manual: {err})",
                  file=sys.stderr)

    eff = staking_mod.effective_apys(config, api_apys)

    for coin in config:
        if coin not in eff:
            print(f"  (skipped {coin} from yield: no APY available from API or config)",
                  file=sys.stderr)

    def usd(coin):
        return (prices.get(coin) or {}).get("usd")

    # Yield table.
    yield_rows = []
    for coin, (apy, source) in eff.items():
        staked = config[coin]["staked_qty"]
        period_crypto, monthly_crypto = staking_mod.projected_yield(staked, apy, days=days)
        price = usd(coin)
        if price is None:
            print(f"  (no live price for {coin}; USD yield omitted)", file=sys.stderr)
            period_usd = monthly_usd = 0.0
        else:
            period_usd = period_crypto * price
            monthly_usd = monthly_crypto * price
        yield_rows.append({"coin": coin, "apy": apy, "source": source,
                           "staked_qty": staked, "period_crypto": period_crypto,
                           "monthly_crypto": monthly_crypto, "period_usd": period_usd,
                           "monthly_usd": monthly_usd})
    print(staking_report.format_yield(yield_rows, days=days))
    print()

    # Realized rewards.
    rewards = staking_mod.load_rewards(rewards_path)
    summary = staking_mod.rewards_summary(rewards)
    reward_rows = []
    rewards_value = 0.0
    for coin, qty in summary.items():
        price = usd(coin) or 0.0
        value = qty * price
        rewards_value += value
        reward_rows.append({"coin": coin, "quantity": qty, "usd_value": value})
    print(staking_report.format_rewards(reward_rows, rewards_value))
    print()

    # Staked vs not staked: annual extra income (days=365 horizon).
    comparison_rows = []
    total_extra = 0.0
    for row in yield_rows:
        annual_crypto = row["staked_qty"] * row["apy"]
        price = usd(row["coin"]) or 0.0
        extra = annual_crypto * price
        total_extra += extra
        comparison_rows.append({"coin": row["coin"], "extra_annual_usd": extra})
    print(staking_report.format_comparison(comparison_rows, total_extra))
    print()

    # Combined P/L: portfolio unrealized profit + realized-reward value.
    held = holdings_mod.load_holdings_or_default(ledger_path, {})
    portfolio_profit = 0.0
    for coin, h in held.items():
        price = usd(coin)
        if price is None:
            continue
        profit = compute_profit(h, price)
        if profit is not None:
            portfolio_profit += profit
    combined = staking_mod.combined_pl(portfolio_profit, rewards_value)
    print(staking_report.format_combined_pl(portfolio_profit, rewards_value, combined))


def build_parser():
    parser = argparse.ArgumentParser(description="Crypto price tracker & tax tool")
    sub = parser.add_subparsers(dest="command")

    imp = sub.add_parser("import", help="import transactions from a CSV file")
    imp.add_argument("csv_file")

    sub.add_parser("add", help="interactively add one transaction")

    tax_cmd = sub.add_parser("tax", help="show realized gains, unrealized P/L, and estimated tax")
    tax_cmd.add_argument("--method", choices=["fifo", "lifo", "average"], default="fifo")
    tax_cmd.add_argument("--year", type=int, default=None)

    reb = sub.add_parser("rebalance", help="allocation, risk, target trades, and backtest")
    reb.add_argument("--strategy", choices=["equal", "marketcap", "custom"], default="equal")
    reb.add_argument("--days", type=int, default=90)

    stk = sub.add_parser("staking", help="staking APY, projected yield, rewards, and combined P/L")
    stk.add_argument("--days", type=int, default=365)

    return parser


def cli(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "import":
        try:
            added, skipped = ledger_mod.import_csv(args.csv_file, LEDGER_PATH)
        except FileNotFoundError:
            print(f"CSV file not found: {args.csv_file}", file=sys.stderr)
            sys.exit(1)
        print(f"Imported {added} transaction(s), skipped {skipped}.")
    elif args.command == "add":
        txn = ledger_mod.add_interactive(LEDGER_PATH)
        print(f"Added: {txn}")
    elif args.command == "tax":
        run_tax(method=args.method, year=args.year)
    elif args.command == "rebalance":
        run_rebalance(strategy=args.strategy, days=args.days)
    elif args.command == "staking":
        run_staking(days=args.days)
    else:
        main()


if __name__ == "__main__":
    cli()
