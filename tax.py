# tax.py
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
        return dict(DEFAULT_CONFIG)
