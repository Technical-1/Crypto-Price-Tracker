import sys

import requests

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
        holdings = originalHoldings

    try:
        priceData = fetch_prices(url)
    except requests.RequestException as err:
        print(f"Failed to fetch prices from CoinGecko: {err}", file=sys.stderr)
        sys.exit(1)

    print("        Coin              Profit      Cost     24hr %")
    print("---------------------   ----------   ------   ---------")

    for key, value in holdings.items():
        coin = priceData.get(key)
        if coin is None or 'usd' not in coin:
            print(f"  (skipped {key}: no price data returned)", file=sys.stderr)
            continue

        profit = compute_profit(value, coin['usd'])
        if profit is None:
            print(f"  (skipped {key}: invalid holding total <= 0)", file=sys.stderr)
            continue

        # A coin may report a price but omit 24h change; show the row anyway,
        # treating the missing change as 0.0% rather than skipping it.
        change = coin.get('usd_24h_change', 0.0)
        print("%20s     %8.2f     %4d      %5.2f" % (
            key, profit, value['cost'], change))


if __name__ == "__main__":
    main()
