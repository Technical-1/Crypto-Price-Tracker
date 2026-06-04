"""Crypto-Price-Tracker — thin CLI orchestrator over coinbasis + cryptolytics.

This module owns argparse, dispatch, and per-command orchestration only.  All
business logic lives in the `coinbasis` and `cryptolytics` packages; all file
and config I/O lives in `appio` / `appconfig`.
"""
from __future__ import annotations

import argparse
import os
import sys

import appio

LEDGER_FILE = "ledger.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crypto-price-tracker",
        description="Track a crypto portfolio: cost basis, tax, valuation, and more.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory holding the data files (default: current directory or CPT_DATA_DIR).",
    )
    sub = parser.add_subparsers(dest="command")

    migrate_p = sub.add_parser(
        "migrate",
        help="Upgrade a legacy V1 ledger.json to the coinbasis multi-wallet schema.",
    )
    migrate_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what migration would do without writing any files.",
    )

    return parser


def _data_dir(args: argparse.Namespace) -> str:
    return args.data_dir or os.environ.get("CPT_DATA_DIR") or os.getcwd()


def _ledger_path(args: argparse.Namespace) -> str:
    return os.path.join(_data_dir(args), LEDGER_FILE)


def cli(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "migrate":
        appio.migrate_command(_ledger_path(args), dry_run=args.dry_run)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(cli())
