# staking_api.py
import requests

POOLS_URL = "https://yields.llama.fi/pools"


def fetch_apys(symbols, timeout=10):
    """Best-effort APY per symbol from DefiLlama yields. For each requested
    symbol, choose the exact-symbol-match pool with the highest tvlUsd and return
    its apy as a fraction (DefiLlama reports apy in percent). Symbols with no
    match are omitted. Raises requests.RequestException on network/HTTP failure."""
    response = requests.get(POOLS_URL, timeout=timeout)
    response.raise_for_status()
    pools = response.json().get("data", [])
    wanted = set(symbols)
    best = {}  # symbol -> (tvl, apy_percent)
    for pool in pools:
        sym = pool.get("symbol")
        if sym not in wanted:
            continue
        apy = pool.get("apy")
        tvl = pool.get("tvlUsd") or 0
        if apy is None:
            continue
        if sym not in best or tvl > best[sym][0]:
            best[sym] = (tvl, apy)
    return {sym: apy_pct / 100 for sym, (tvl, apy_pct) in best.items()}
