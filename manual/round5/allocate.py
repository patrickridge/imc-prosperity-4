"""
Round 5 manual challenge allocator.

Fee formula: fee_i = (volume_pct_i / 100)^2 * budget
Profit:    profit_i = w_i * r_i * B - w_i^2 * B
where w_i = volume_pct_i / 100 (signed; positive = long, negative = short)

Single-product optimum: w_i* = r_i / 2
Budget constraint:      sum(|w_i|) <= 1

If sum(|r_i|/2) > 1, scale all positions by 1 / sum(|r_i|/2).
"""

BUDGET = 1_000_000
MAX_SINGLE_POSITION = 0.25  # cap any single bet at 25% of budget
HEDGE_FACTOR = 0.75         # take 75% of theoretical optimal (P3 lesson)

# TODO (team): fill in expected % moves. Positive = up, negative = down.
# P3 hedgehogs used ranges of ±5% to ±50%. Reference their table in
# docs/reference/prosperity-3-hedgehogs.md for calibration.
expected_returns = {
    "LAVA_FOUNTAIN_PEN":    0.05,
    "THERMALITE_CORE":      0.25,
    "SCORIA_PASTE":         0.00,
    "VOLCANIC_INCENSE":     0.00,
    "SULFUR_LTD":           0.15,
    "OBSIDIAN_CUTLERY":    -0.20,
    "PYROFLEX_CELL":       -0.15,
    "ASHES_OF_THE_PHOENIX": -0.20,
    "LAVA_CAKES":          -0.30,
}


def compute_allocations(returns: dict[str, float]) -> dict[str, float]:
    raw_weights = {p: r / 2 for p, r in returns.items()}
    capped = {p: max(-MAX_SINGLE_POSITION, min(MAX_SINGLE_POSITION, w))
              for p, w in raw_weights.items()}
    total = sum(abs(w) for w in capped.values())
    scale = min(1.0, 1.0 / total) if total > 0 else 1.0
    return {p: w * scale * HEDGE_FACTOR for p, w in capped.items()}


def expected_pnl(weights: dict[str, float], returns: dict[str, float]) -> float:
    return sum(w * returns[p] - w * w for p, w in weights.items()) * BUDGET


def main():
    if any(v is None for v in expected_returns.values()):
        print("Fill in expected_returns first (None values remain).")
        return

    weights = compute_allocations(expected_returns)
    pnl = expected_pnl(weights, expected_returns)

    print(f"{'Product':<25} {'r_i':>7} {'volume_pct':>11} {'fee':>10} {'profit':>10}")
    print("-" * 67)
    for p, w in weights.items():
        r = expected_returns[p]
        fee = w * w * BUDGET
        profit = (w * r - w * w) * BUDGET
        side = "LONG" if w > 0 else "SHORT" if w < 0 else "—"
        print(f"{p:<25} {r:>+7.1%} {w*100:>+10.1f}% {fee:>10,.0f} {profit:>+10,.0f}")
    print("-" * 67)
    used = sum(abs(w) for w in weights.values())
    print(f"{'Budget used':<25} {used*100:>10.1f}%")
    print(f"{'Expected PnL':<25} {pnl:>+10,.0f}")


if __name__ == "__main__":
    main()
