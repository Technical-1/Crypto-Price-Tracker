# chart.py
BLOCKS = "▁▂▃▄▅▆▇█"  # ▁▂▃▄▅▆▇█


def sparkline(values):
    """Render values as a single line of Unicode block glyphs scaled min->max.
    Empty -> ''. All-equal -> a uniform mid glyph per value."""
    if not values:
        return ""
    lo = min(values)
    hi = max(values)
    if hi == lo:
        mid = BLOCKS[len(BLOCKS) // 2]
        return mid * len(values)
    span = hi - lo
    out = []
    for v in values:
        idx = int((v - lo) / span * (len(BLOCKS) - 1))
        out.append(BLOCKS[idx])
    return "".join(out)


def hbar(value, max_abs, width):
    """Horizontal bar of '█' scaled by |value|/max_abs to `width` columns.
    Negative values are prefixed with '-'. Zero or max_abs<=0 -> empty bar."""
    if max_abs <= 0 or value == 0:
        return " " * width
    filled = int(min(abs(value) / max_abs, 1.0) * width)
    sign = "-" if value < 0 else " "
    return sign + "█" * filled
