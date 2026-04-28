"""Round 5 manual submission helper.

Defines base / aggressive / conservative sentiment estimates for the 9 Ignith
goods, runs the allocator on each scenario, prints a recommendation table.

Run as: python3 manual/round5/sentiment_estimates.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from allocate import compute_allocations, expected_pnl, BUDGET

# Base case: signed expected % moves over the 1-day hold.
# Calibrated from headline strength + P3 hedgehogs' rule of thumb (typical
# moves ±5% to ±50%, hedge below estimates because some news is priced in).
BASE = {
    "LAVA_FOUNTAIN_PEN":    +0.05,   # hot drop + merger, niche product
    "THERMALITE_CORE":      +0.20,   # only headline with a number: 1.42M -> 3.89M users
    "SCORIA_PASTE":         +0.10,   # influencer urging stockpile before "unaffordable"
    "VOLCANIC_INCENSE":     +0.10,   # influencer publicly accelerating buys
    "SULFUR_LTD":           +0.15,   # mechanical index inclusion -> forced rebalance buying
    "OBSIDIAN_CUTLERY":     -0.10,   # production halted, contamination
    "PYROFLEX_CELL":        -0.15,   # tax cut canceled, levy doubles
    "ASHES_OF_THE_PHOENIX": -0.10,   # PR scandal (PR scandals often fade)
    "LAVA_CAKES":           -0.15,   # actual lava found + lawsuits
}

AGGRESSIVE = {p: r * 1.5 for p, r in BASE.items()}
CONSERVATIVE = {p: r * 0.5 for p, r in BASE.items()}

SCENARIOS = {
    "AGGRESSIVE (1.5x base)": AGGRESSIVE,
    "BASE":                    BASE,
    "CONSERVATIVE (0.5x base)": CONSERVATIVE,
}


def print_table(name: str, returns: dict[str, float]) -> tuple[float, float]:
    weights = compute_allocations(returns)
    pnl = expected_pnl(weights, returns)
    used = sum(abs(w) for w in weights.values())

    print(f"\n=== {name} ===")
    print(f"{'product':<25} {'r_i':>7} {'volume_pct':>11}")
    print("-" * 47)
    for p, w in weights.items():
        r = returns[p]
        print(f"{p:<25} {r:>+7.1%} {w*100:>+10.2f}%")
    print(f"{'budget used':<25} {'':>7} {used*100:>10.1f}%")
    print(f"{'expected PnL':<25} {'':>7} {pnl:>+10,.0f}")
    return used, pnl


def main() -> None:
    print("=" * 78)
    print("Round 5 manual: sentiment estimates and recommended submission")
    print("=" * 78)
    print("Base case is the recommended submission. Aggressive overweights;")
    print("conservative underutilizes the budget.")

    summary = []
    for name, returns in SCENARIOS.items():
        used, pnl = print_table(name, returns)
        summary.append((name, used, pnl))

    print()
    print("=" * 78)
    print("Sensitivity summary")
    print("=" * 78)
    print(f"{'scenario':<32} {'budget used':>13} {'expected PnL':>14}")
    print("-" * 60)
    for name, used, pnl in summary:
        print(f"{name:<32} {used*100:>12.1f}% {pnl:>+14,.0f}")

    print()
    print("Recommendation: submit the BASE case numbers above.")
    print("Aggressive PnL is higher but assumes narratives play out fully —")
    print("P3 hedgehogs scored 65% of optimal precisely because they overestimated.")


if __name__ == "__main__":
    main()
