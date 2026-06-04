"""Environment / XDG wiring → AppContext.

This is the only place in the app that reads env vars. Everything downstream
receives an AppContext; they never call os.environ directly.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

import coinbasis
import coinbasis.serde as _serde
import cryptolytics

# ── Method mapping ────────────────────────────────────────────────────────────
_METHOD_MAP: dict[str, coinbasis.CostBasisMethod] = {
    "fifo":    coinbasis.CostBasisMethod.FIFO,
    "lifo":    coinbasis.CostBasisMethod.LIFO,
    "hifo":    coinbasis.CostBasisMethod.HIFO,
    "average": coinbasis.CostBasisMethod.AVERAGE,
    # "specific" handled below (requires --select)
}


@dataclass(frozen=True)
class AppContext:
    paths: dict            # {"ledger": str, "taxconfig": str, ...}
    cg_config: cryptolytics.CoinGeckoConfig
    method: coinbasis.CostBasisMethod   # the resolved cost-basis method (FIFO when specific)
    method_is_specific: bool            # True when --method specific was chosen
    lot_selection: Optional[coinbasis.LotSelection]
    offline: bool


def _xdg_cache() -> str:
    """Return XDG_CACHE_HOME or ~/.cache."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    return xdg if xdg else os.path.join(os.path.expanduser("~"), ".cache")


def build_context_from_env(
    *,
    data_dir: Optional[str],
    method: str,
    select_file: Optional[str],
    offline: bool,
) -> AppContext:
    """Build AppContext from env + CLI flags.

    data_dir priority: --data-dir arg > CPT_DATA_DIR env > CWD.
    api_key: COINGECKO_API_KEY; plan: COINGECKO_PLAN (default 'demo').
    """
    # Resolve data directory
    resolved_dir = (
        data_dir
        or os.environ.get("CPT_DATA_DIR")
        or os.getcwd()
    )

    def _path(filename: str) -> str:
        return os.path.join(resolved_dir, filename)

    paths = {
        "ledger":    _path("ledger.json"),
        "taxconfig": _path("taxconfig.json"),
        "targets":   _path("targets.json"),
        "staking":   _path("staking.json"),
        "rewards":   _path("rewards.csv"),
        "news":      _path("news.json"),
        "snapshots": _path("snapshots.jsonl"),
    }

    # CoinGecko config from env
    api_key = os.environ.get("COINGECKO_API_KEY") or None
    plan    = os.environ.get("COINGECKO_PLAN", "demo")
    cache_dir = os.path.join(_xdg_cache(), "crypto-price-tracker", "prices")
    cg_config = cryptolytics.CoinGeckoConfig(
        api_key=api_key,
        plan=plan,
        cache_dir=cache_dir,
        # remaining fields use CoinGeckoConfig defaults
    )

    # Resolve method + selection
    method_lower = method.lower()
    lot_selection: Optional[coinbasis.LotSelection] = None
    method_is_specific = method_lower == "specific"

    if method_is_specific:
        if not select_file:
            print(
                "--method specific requires --select FILE (a LotSelection JSON file). "
                "Use an automatic method (fifo/lifo/hifo/average) if you don't have one.",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            with open(select_file) as f:
                lot_selection = _serde.lot_selection_from_json(f.read())
        except (OSError, ValueError) as exc:
            print(f"Cannot load --select file {select_file}: {exc}", file=sys.stderr)
            sys.exit(1)
        resolved_method = coinbasis.CostBasisMethod.FIFO  # placeholder; orchestrators use selection path
    else:
        if method_lower not in _METHOD_MAP:
            print(
                f"Unknown --method '{method}'. "
                f"Choose from: fifo, lifo, hifo, average, specific.",
                file=sys.stderr,
            )
            sys.exit(1)
        resolved_method = _METHOD_MAP[method_lower]

    return AppContext(
        paths=paths,
        cg_config=cg_config,
        method=resolved_method,
        method_is_specific=method_is_specific,
        lot_selection=lot_selection,
        offline=offline,
    )
