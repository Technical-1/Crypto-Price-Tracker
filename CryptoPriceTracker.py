"""Crypto-Price-Tracker — thin orchestrator over coinbasis + cryptolytics."""
from __future__ import annotations

import argparse
import sys
from typing import Optional

import coinbasis
import cryptolytics

import appio
import appconfig
import report
import rebalance_report
import staking_report
import news_report
import history_report
import perf_report
import chart

# ── Legacy demo fallback (kept for backward-compat when ledger is absent) ─────
originalHoldings = {
    "ethereum":          {"total": 1, "cost": 200},
    "bitcoin":           {"total": 1, "cost": 200},
    "1inch":             {"total": 1, "cost": 20},
    "the-graph":         {"total": 1, "cost": 20},
    "decentraland":      {"total": 1, "cost": 20},
    "uniswap":           {"total": 1, "cost": 20},
}


def build_parser() -> argparse.ArgumentParser:
    """Build the full argument parser with global flags + all subcommands."""
    # Global (shared) options added to every subcommand via parents=
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--method",
        choices=["fifo", "lifo", "hifo", "average", "specific"],
        default="fifo",
        help="Cost-basis method (default: fifo)",
    )
    parent.add_argument("--select", metavar="FILE", default=None,
                        help="Lot-selection JSON file (required with --method specific)")
    parent.add_argument("--wallet", metavar="NAME", default=None,
                        help="Filter output to a single wallet")
    parent.add_argument("--year", type=int, default=None,
                        help="Calendar-year filter (e.g. 2024)")
    parent.add_argument("--offline", action="store_true",
                        help="Never fetch; use cached prices only")
    parent.add_argument("--no-migrate", action="store_true",
                        help="Skip automatic V1 ledger migration")

    main = argparse.ArgumentParser(
        prog="crypto-price-tracker",
        description="Crypto portfolio tracker (coinbasis + cryptolytics)",
    )
    main.add_argument("--data-dir", metavar="DIR", default=None,
                      help="Data directory (default: CWD; env: CPT_DATA_DIR)")
    main.add_argument("--quiet", action="store_true",
                      help="Suppress informational stderr notices")

    subs = main.add_subparsers(dest="command")

    # prices
    p_prices = subs.add_parser("prices", parents=[parent],
                               help="Current prices and unrealized P/L")
    p_prices.add_argument("--sparkline", action="store_true",
                          help="Fetch and display 7-day sparklines")

    # holdings
    p_holdings = subs.add_parser("holdings", parents=[parent],
                                 help="Open lots (holdings) per wallet")
    p_holdings.add_argument("--group", choices=["asset", "wallet"], default="asset",
                            help="Group by asset (default) or wallet")

    # valuation
    subs.add_parser("valuation", parents=[parent],
                    help="Portfolio valuation and allocation chart")

    # tax
    subs.add_parser("tax", parents=[parent],
                    help="Capital gains / income / estimated tax")

    # rebalance
    p_reb = subs.add_parser("rebalance", parents=[parent],
                            help="Rebalance to target allocation")
    p_reb.add_argument("--strategy", choices=["equal", "marketcap", "custom"],
                       default="equal")
    p_reb.add_argument("--band", type=float, default=0.05,
                       help="Drift band threshold (default 5%%)")
    p_reb.add_argument("--full", action="store_true",
                       help="Full rebalance (trade every off-target asset)")
    p_reb.add_argument("--days", type=int, default=90,
                       help="History days for risk analytics (default 90)")

    # performance
    p_perf = subs.add_parser("performance", parents=[parent],
                             help="Portfolio performance metrics + sparkline")
    p_perf.add_argument("--days", type=int, default=90)
    p_perf.add_argument("--risk-free", type=float, default=0.0,
                        help="Annual risk-free rate for Sharpe (default 0)")

    # staking
    p_stk = subs.add_parser("staking", parents=[parent],
                            help="Staking APY and projected yield")
    p_stk.add_argument("--days", type=int, default=365)

    # news
    p_news = subs.add_parser("news", parents=[parent],
                             help="Crypto news with sentiment")
    p_news.add_argument("--coin", metavar="COIN", default=None)
    p_news.add_argument("--limit", type=int, default=20)

    # history
    p_hist = subs.add_parser("history", parents=[parent],
                             help="Historical portfolio value chart")
    p_hist.add_argument("--days", type=int, default=90)
    p_hist.add_argument("--date", metavar="YYYY-MM-DD", default=None)
    p_hist.add_argument("--play", action="store_true")

    # import
    p_imp = subs.add_parser("import", help="Import transactions from CSV")
    p_imp.add_argument("file", metavar="FILE.csv")

    # add
    subs.add_parser("add", help="Interactively add a transaction")

    # migrate
    p_mig = subs.add_parser("migrate", help="Upgrade V1 ledger to coinbasis schema")
    p_mig.add_argument("--dry-run", action="store_true")

    return main


def cli(argv: Optional[list[str]] = None) -> None:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    cmd = getattr(args, "command", None)

    if cmd == "migrate":
        ctx = _build_ctx(args)
        appio.migrate_command(ctx.paths["ledger"],
                              dry_run=getattr(args, "dry_run", False))
        return

    if cmd == "import":
        ctx = _build_ctx(args)
        appio.import_csv(args.file, ctx.paths["ledger"])
        return

    if cmd == "add":
        ctx = _build_ctx(args)
        _run_add(ctx)
        return

    # All data commands share the same AppContext pattern
    ctx = _build_ctx(args)
    if cmd == "prices" or cmd is None:
        run_prices(ctx, args)
    elif cmd == "holdings":
        run_holdings(ctx, args)
    elif cmd == "valuation":
        run_valuation(ctx, args)
    elif cmd == "tax":
        run_tax(ctx, args)
    elif cmd == "rebalance":
        run_rebalance(ctx, args)
    elif cmd == "performance":
        run_performance(ctx, args)
    elif cmd == "staking":
        run_staking(ctx, args)
    elif cmd == "news":
        run_news(ctx, args)
    elif cmd == "history":
        run_history(ctx, args)
    else:
        parser.print_help()
        sys.exit(2)


def _build_ctx(args: argparse.Namespace) -> appconfig.AppContext:
    return appconfig.build_context_from_env(
        data_dir=getattr(args, "data_dir", None),
        method=getattr(args, "method", "fifo"),
        select_file=getattr(args, "select", None),
        offline=getattr(args, "offline", False),
    )


# ── Orchestrators ─────────────────────────────────────────────────────────────

def run_prices(ctx: appconfig.AppContext, args: argparse.Namespace) -> None:
    """Stub — implemented in Part 4 (Task 23)."""
    raise NotImplementedError("run_prices: see plan-04 Task 23")


def run_holdings(ctx: appconfig.AppContext, args: argparse.Namespace) -> None:
    raise NotImplementedError("run_holdings: see plan-04 Task 23")


def run_valuation(ctx: appconfig.AppContext, args: argparse.Namespace) -> None:
    raise NotImplementedError("run_valuation: see plan-04 Task 24")


def run_tax(ctx: appconfig.AppContext, args: argparse.Namespace) -> None:
    raise NotImplementedError("run_tax: see plan-03 Task 20")


def run_rebalance(ctx: appconfig.AppContext, args: argparse.Namespace) -> None:
    raise NotImplementedError("run_rebalance: see plan-03 Task 21")


def run_performance(ctx: appconfig.AppContext, args: argparse.Namespace) -> None:
    raise NotImplementedError("run_performance: see plan-04 Task 26")


def run_staking(ctx: appconfig.AppContext, args: argparse.Namespace) -> None:
    raise NotImplementedError("run_staking: see plan-03 Task 22")


def run_news(ctx: appconfig.AppContext, args: argparse.Namespace) -> None:
    raise NotImplementedError("run_news: see plan-03 Task 22")


def run_history(ctx: appconfig.AppContext, args: argparse.Namespace) -> None:
    raise NotImplementedError("run_history: see plan-03 Task 22")


def _run_add(ctx: appconfig.AppContext) -> None:
    raise NotImplementedError("add: see plan-03 Task 19")


if __name__ == "__main__":
    cli()
