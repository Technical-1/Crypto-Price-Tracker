# staking_report.py


def format_staking(
    eff_apys: dict,
    rewards_summary: dict,
    config: dict,
    projected: dict | None = None,
) -> str:
    lines = ["Staking Summary"]
    header = f"{'Coin':<12} {'APY':>8} {'Source':<10} {'Rewards':>10} {'Est.Annual':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for coin, (apy, source) in sorted(eff_apys.items()):
        staked = float(config.get(coin, {}).get("staked_qty", 0))
        annual = staked * apy
        rwds = rewards_summary.get(coin, 0)
        lines.append(
            f"{coin:<12} {apy*100:>7.2f}% {source:<10} {rwds:>10.4f} {annual:>12.4f}"
        )
    return "\n".join(lines) + "\n"
