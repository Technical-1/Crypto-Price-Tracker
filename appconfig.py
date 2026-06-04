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
import coinbasis.serialization as _serde
import coinlytics

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
    cg_config: coinlytics.CoinGeckoConfig
    method: coinbasis.CostBasisMethod   # the resolved cost-basis method (FIFO when specific)
    method_is_specific: bool            # True when --method specific was chosen
    lot_selection: Optional[coinbasis.LotSelection]
    offline: bool


def _xdg_cache() -> str:
    """Return XDG_CACHE_HOME or ~/.cache."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    return xdg if xdg else os.path.join(os.path.expanduser("~"), ".cache")


def _xdg_config() -> str:
    """Return XDG_CONFIG_HOME or ~/.config."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return xdg if xdg else os.path.join(os.path.expanduser("~"), ".config")


def resolve_data_dir(
    *,
    data_dir: Optional[str],
    env_dir: Optional[str],
    cwd: str,
    xdg_config_home: str,
) -> tuple[str, bool]:
    """Decide which directory holds ledger.json and the optional configs.

    Precedence (so a global install works from any working directory):
      1. --data-dir (explicit)
      2. CPT_DATA_DIR env
      3. the current directory, when it already holds a ledger.json
      4. the global <xdg_config_home>/crypto-price-tracker/ directory

    Pure: every input is injected and no filesystem writes happen here.
    Returns (dir, used_global); used_global is True only for case 4, so the
    caller can create that directory and announce it on first run.
    """
    if data_dir:
        return data_dir, False
    if env_dir:
        return env_dir, False
    if os.path.exists(os.path.join(cwd, "ledger.json")):
        return cwd, False
    return os.path.join(xdg_config_home, "crypto-price-tracker"), True


def build_context_from_env(
    *,
    data_dir: Optional[str],
    method: str,
    select_file: Optional[str],
    offline: bool,
    quiet: bool = False,
) -> AppContext:
    """Build AppContext from env + CLI flags.

    data_dir priority: --data-dir arg > CPT_DATA_DIR env > ./ledger.json's
    directory > ~/.config/crypto-price-tracker/ (created on first use).
    api_key: COINGECKO_API_KEY; plan: COINGECKO_PLAN (default 'demo').
    """
    # Resolve the data directory (see resolve_data_dir for precedence).
    resolved_dir, used_global = resolve_data_dir(
        data_dir=data_dir,
        env_dir=os.environ.get("CPT_DATA_DIR"),
        cwd=os.getcwd(),
        xdg_config_home=_xdg_config(),
    )
    if used_global:
        first_run = not os.path.isdir(resolved_dir)
        os.makedirs(resolved_dir, exist_ok=True)
        if first_run and not quiet:
            print(
                f"Using global data directory {resolved_dir} "
                "(no ledger.json in the current directory; set --data-dir or "
                "CPT_DATA_DIR to override).",
                file=sys.stderr,
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
    cg_kwargs = dict(api_key=api_key, plan=plan, cache_dir=cache_dir)
    if offline:
        # Make all cached prices appear fresh so the client never hits the network;
        # any cache miss surfaces as a stale PriceBook rather than a live fetch.
        cg_kwargs["cache_ttl"] = sys.maxsize
        cg_kwargs["history_cache_ttl"] = sys.maxsize
    cg_config = coinlytics.CoinGeckoConfig(**cg_kwargs)

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
