# tests/test_costbasis.py
import costbasis
from ledger import Transaction


def test_fifo_single_buy_then_full_sell():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-02-01", "bitcoin", "sell", 1.0, 150.0, 0.0),
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert len(disposals) == 1
    d = disposals[0]
    assert d.coin == "bitcoin"
    assert d.quantity == 1.0
    assert d.proceeds == 150.0
    assert d.cost_basis == 100.0
    assert d.realized_gain == 50.0
    assert d.term == "short"
    assert remaining.get("bitcoin", []) == []


def test_fifo_consumes_oldest_lot_first_across_two_lots():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-03-01", "bitcoin", "buy", 1.0, 200.0, 0.0),
        Transaction("2024-04-01", "bitcoin", "sell", 1.0, 300.0, 0.0),
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert len(disposals) == 1
    assert disposals[0].cost_basis == 100.0     # oldest lot consumed
    assert disposals[0].realized_gain == 200.0
    assert len(remaining["bitcoin"]) == 1
    assert remaining["bitcoin"][0].quantity == 1.0
    assert remaining["bitcoin"][0].basis_per_unit == 200.0


def test_fifo_partial_lot_sell_splits_remaining():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 2.0, 100.0, 0.0),   # basis 50/unit
        Transaction("2024-02-01", "bitcoin", "sell", 0.5, 80.0, 0.0),
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert disposals[0].quantity == 0.5
    assert disposals[0].cost_basis == 25.0       # 0.5 * 50
    assert disposals[0].proceeds == 40.0         # 0.5 * 80
    assert remaining["bitcoin"][0].quantity == 1.5


def test_buy_fee_raises_basis_sell_fee_lowers_proceeds():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 10.0),  # basis 110
        Transaction("2024-02-01", "bitcoin", "sell", 1.0, 200.0, 20.0), # proceeds 180
    ]
    disposals, _ = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert disposals[0].cost_basis == 110.0
    assert disposals[0].proceeds == 180.0
    assert disposals[0].realized_gain == 70.0


def test_long_term_boundary_at_366_days():
    txns = [
        Transaction("2023-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-01-01", "bitcoin", "sell", 0.5, 150.0, 0.0),  # 365 days -> short
        Transaction("2024-01-02", "bitcoin", "sell", 0.5, 150.0, 0.0),  # 366 days -> long
    ]
    disposals, _ = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    assert disposals[0].holding_days == 365
    assert disposals[0].term == "short"
    assert disposals[1].holding_days == 366
    assert disposals[1].term == "long"


def test_oversell_is_skipped_with_notice(capsys):
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-02-01", "bitcoin", "sell", 2.0, 150.0, 0.0),  # only 1.0 held
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="fifo", long_term_threshold=365)
    # the 1.0 actually held is disposed; the excess 1.0 is reported and dropped
    assert sum(d.quantity for d in disposals) == 1.0
    assert "bitcoin" in capsys.readouterr().err
    assert remaining.get("bitcoin", []) == []


def test_lifo_consumes_newest_lot_first():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-03-01", "bitcoin", "buy", 1.0, 200.0, 0.0),
        Transaction("2024-04-01", "bitcoin", "sell", 1.0, 300.0, 0.0),
    ]
    disposals, remaining = costbasis.process_ledger(txns, method="lifo", long_term_threshold=365)
    assert disposals[0].cost_basis == 200.0     # newest lot consumed
    assert disposals[0].realized_gain == 100.0
    assert remaining["bitcoin"][0].basis_per_unit == 100.0  # oldest lot remains


def test_average_uses_pooled_basis():
    txns = [
        Transaction("2024-01-01", "bitcoin", "buy", 1.0, 100.0, 0.0),
        Transaction("2024-03-01", "bitcoin", "buy", 3.0, 300.0, 0.0),  # 300 for 3 -> 100/unit
        Transaction("2024-04-01", "bitcoin", "sell", 2.0, 250.0, 0.0),
    ]
    # pooled basis = (100 + 900)/4 = 250 total / ... per-unit = (100*1 + 100*3)/4 = 100
    disposals, _ = costbasis.process_ledger(txns, method="average", long_term_threshold=365)
    assert sum(d.cost_basis for d in disposals) == 200.0   # 2 units * 100 avg
    assert sum(d.proceeds for d in disposals) == 500.0     # 2 * 250
    assert sum(d.realized_gain for d in disposals) == 300.0
