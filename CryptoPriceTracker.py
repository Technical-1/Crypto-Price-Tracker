import argparse
import sys

import requests

import ledger as ledger_mod
import holdings as holdings_mod
import costbasis
import tax as tax_mod
import report

LEDGER_PATH = "ledger.json"
TAXCONFIG_PATH = "taxconfig.json"

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


def build_parser():
    parser = argparse.ArgumentParser(description="Crypto price tracker & tax tool")
    sub = parser.add_subparsers(dest="command")

    imp = sub.add_parser("import", help="import transactions from a CSV file")
    imp.add_argument("csv_file")

    sub.add_parser("add", help="interactively add one transaction")

    tax_cmd = sub.add_parser("tax", help="show realized gains, unrealized P/L, and estimated tax")
    tax_cmd.add_argument("--method", choices=["fifo", "lifo", "average"], default="fifo")
    tax_cmd.add_argument("--year", type=int, default=None)

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
    else:
        main()


if __name__ == "__main__":
    cli()
