"""Verify the round 5 manual allocator math.

The allocator solves: maximise sum(w_i * r_i - w_i^2) * B
subject to sum(|w_i|) <= 1 and |w_i| <= MAX_SINGLE_POSITION.

This script asserts the closed-form properties hold across edge cases.
Run as: python3 manual/round5/verify_allocator.py

Exits non-zero if any assertion fails.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from allocate import (
    BUDGET, HEDGE_FACTOR, MAX_SINGLE_POSITION,
    compute_allocations, expected_pnl,
)

TOL = 1e-9


def _check(name: str, actual, expected, tol: float = TOL) -> None:
    diff = abs(actual - expected) if isinstance(actual, (int, float)) else None
    ok = diff is not None and diff < tol
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {name}: got {actual}, expected {expected}")
    if not ok:
        sys.exit(1)


def test_single_product_unconstrained_optimum() -> None:
    """For a lone product with r in [0, 0.4], optimum is w = r/2."""
    print("test_single_product_unconstrained_optimum")
    for r in [0.05, 0.10, 0.20, 0.30, 0.40]:
        w = compute_allocations({"X": r})["X"]
        expected = (r / 2) * HEDGE_FACTOR
        _check(f"r={r:+.2f}", w, expected)


def test_single_product_capped() -> None:
    """For r > 2 * MAX_SINGLE_POSITION, allocation must hit the cap."""
    print("test_single_product_capped")
    big_r = 0.80
    w = compute_allocations({"X": big_r})["X"]
    expected = MAX_SINGLE_POSITION * HEDGE_FACTOR
    _check(f"r={big_r}", w, expected)


def test_short_side_symmetric() -> None:
    """Negative r should give symmetric negative w."""
    print("test_short_side_symmetric")
    for r in [-0.10, -0.20, -0.30]:
        w = compute_allocations({"X": r})["X"]
        expected = (r / 2) * HEDGE_FACTOR
        _check(f"r={r:+.2f}", w, expected)


def test_zero_returns_zero_allocation() -> None:
    """If every r_i is 0, every allocation should be 0."""
    print("test_zero_returns_zero_allocation")
    weights = compute_allocations({f"P{i}": 0.0 for i in range(9)})
    total = sum(abs(w) for w in weights.values())
    _check("sum |w|", total, 0.0)


def test_budget_constraint_holds() -> None:
    """sum(|w|) must never exceed 1, even with extreme returns."""
    print("test_budget_constraint_holds")
    extreme = {f"P{i}": 0.50 for i in range(9)}  # 9 longs, all r=50%
    weights = compute_allocations(extreme)
    total = sum(abs(w) for w in weights.values())
    assert total <= 1.0 + TOL, f"sum |w| = {total} exceeds 1"
    print(f"  [PASS] sum |w| = {total:.4f} <= 1.0")


def test_pnl_formula_matches() -> None:
    """expected_pnl must equal sum(w * r - w^2) * BUDGET to floating tolerance."""
    print("test_pnl_formula_matches")
    rs = {"A": 0.30, "B": -0.20, "C": 0.10, "D": -0.05}
    ws = compute_allocations(rs)
    direct = sum(ws[p] * rs[p] - ws[p] ** 2 for p in rs) * BUDGET
    via_func = expected_pnl(ws, rs)
    _check("pnl", via_func, direct, tol=1e-6)


def test_hedge_factor_applied() -> None:
    """When uncapped + unconstrained, w should equal r/2 * HEDGE_FACTOR."""
    print("test_hedge_factor_applied")
    r = 0.10
    w = compute_allocations({"X": r})["X"]
    raw_optimum = r / 2
    expected = raw_optimum * HEDGE_FACTOR
    assert abs(w - raw_optimum) > TOL, "hedge factor not applied"
    _check(f"hedged w (r=0.10)", w, expected)


def test_realistic_9_product_portfolio() -> None:
    """Sanity-check on a realistic 9-product mix (5 longs, 4 shorts)."""
    print("test_realistic_9_product_portfolio")
    rs = {
        "LAVA_FOUNTAIN_PEN": 0.10,
        "THERMALITE_CORE":   0.20,
        "SCORIA_PASTE":      0.10,
        "VOLCANIC_INCENSE":  0.10,
        "SULFUR_LTD":        0.15,
        "OBSIDIAN_CUTLERY":  -0.10,
        "PYROFLEX_CELL":     -0.15,
        "ASHES_OF_THE_PHOENIX": -0.10,
        "LAVA_CAKES":        -0.15,
    }
    ws = compute_allocations(rs)
    total = sum(abs(w) for w in ws.values())
    pnl = expected_pnl(ws, rs)
    assert total <= 1.0 + TOL, f"budget exceeded: {total}"
    assert pnl > 0, f"realistic mixed portfolio should be profitable: {pnl}"
    print(f"  [PASS] sum |w| = {total:.4f}, pnl = {pnl:+,.0f}")


def main() -> None:
    print("Verifying round 5 manual allocator (manual/round5/allocate.py)...")
    print()
    test_single_product_unconstrained_optimum()
    test_single_product_capped()
    test_short_side_symmetric()
    test_zero_returns_zero_allocation()
    test_budget_constraint_holds()
    test_pnl_formula_matches()
    test_hedge_factor_applied()
    test_realistic_9_product_portfolio()
    print()
    print("All allocator checks passed.")


if __name__ == "__main__":
    main()
