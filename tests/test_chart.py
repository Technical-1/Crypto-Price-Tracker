# tests/test_chart.py
import chart


def test_sparkline_empty():
    assert chart.sparkline([]) == ""


def test_sparkline_all_equal_uses_uniform_glyph():
    out = chart.sparkline([5.0, 5.0, 5.0])
    assert len(out) == 3
    assert len(set(out)) == 1          # all the same glyph


def test_sparkline_scales_min_to_max():
    # ascending values -> non-decreasing glyph heights; min maps to first block,
    # max to last block in the ramp
    out = chart.sparkline([1.0, 2.0, 3.0, 4.0])
    assert len(out) == 4
    ramp = "▁▂▃▄▅▆▇█"
    assert out[0] == ramp[0]           # min -> lowest block
    assert out[-1] == ramp[-1]         # max -> highest block
    assert ramp.index(out[0]) <= ramp.index(out[1]) <= ramp.index(out[2]) <= ramp.index(out[3])


def test_hbar_positive_scales_to_width():
    bar = chart.hbar(5.0, 10.0, width=10)
    assert bar.count("█") == 5    # half of width


def test_hbar_zero_or_no_scale_is_empty():
    assert chart.hbar(0.0, 10.0, width=10).strip() == ""
    assert chart.hbar(5.0, 0.0, width=10).strip() == ""


def test_hbar_negative_marks_direction():
    bar = chart.hbar(-5.0, 10.0, width=10)
    assert "-" in bar                  # negative direction indicated
    assert bar.count("█") == 5
