# tax.py
import copy
import json
import sys

DEFAULT_CONFIG = {
    "jurisdiction": "default",
    "long_term_threshold_days": 365,
    "short_term_rate": 0.35,
    "long_term_brackets": [{"up_to": None, "rate": 0.15}],
}

REQUIRED_KEYS = ("long_term_threshold_days", "short_term_rate", "long_term_brackets")


def load_tax_config(path):
    """Load the tax config JSON, falling back to DEFAULT_CONFIG (with a stderr
    warning) if the file is missing, unreadable, or missing required keys."""
    try:
        with open(path) as f:
            cfg = json.load(f)
        for key in REQUIRED_KEYS:
            if key not in cfg:
                raise KeyError(key)
        return cfg
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as err:
        print(f"Warning: using default tax config ({err})", file=sys.stderr)
        return copy.deepcopy(DEFAULT_CONFIG)


def summarize(disposals, year=None):
    """Return (short_gain, long_gain) summed across disposals, optionally
    filtered to those whose sell_date falls in the given calendar year."""
    selected = disposals
    if year is not None:
        selected = [d for d in disposals if d.sell_date[:4] == str(year)]
    short = sum(d.realized_gain for d in selected if d.term == "short")
    long = sum(d.realized_gain for d in selected if d.term == "long")
    return short, long


def estimate_long_term_tax(gain, brackets):
    """Apply progressive bracket rates to a non-negative long-term gain."""
    if gain <= 0:
        return 0.0
    tax_due = 0.0
    lower = 0.0
    for b in brackets:
        upper = b["up_to"] if b["up_to"] is not None else float("inf")
        if gain <= lower:
            break
        taxable = min(gain, upper) - lower
        tax_due += taxable * b["rate"]
        lower = upper
    return tax_due


def estimate_tax(short_gain, long_gain, config):
    """Return (short_term_tax, long_term_tax). Net losses produce zero tax."""
    st = max(0.0, short_gain) * config["short_term_rate"]
    lt = estimate_long_term_tax(max(0.0, long_gain), config["long_term_brackets"])
    return st, lt
