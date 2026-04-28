"""H3 (Round 5): Are PANEL prices linked by composition?

PANEL sizes are 1x2, 2x2, 1x4, 2x4, 4x4 — areas of 2, 4, 4, 8, 16 square units.
If the market prices these by composition, basket-style relationships should hold:
    PANEL_1X4  ≈  PANEL_2X2     (both 4 sq units)
    PANEL_2X4  ≈  2 × PANEL_2X2 ≈ 2 × PANEL_1X4   (8 sq units)
    PANEL_4X4  ≈  2 × PANEL_2X4                    (16 sq units)

Tradeable arb when the market deviates from these identities and reverts.

Run as: python3 research/round5_h3_panel_basket.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]

# (display name, expr)
# expr is a tuple of (coefficient, product) pairs that should sum to ~0
# e.g. ("1X4 ≈ 2X2", [(+1, "PANEL_1X4"), (-1, "PANEL_2X2")])
RELATIONS = [
    ("PANEL_1X4 vs PANEL_2X2  (both 4 sq)",     [(+1, "PANEL_1X4"), (-1, "PANEL_2X2")]),
    ("PANEL_2X4 vs 2*PANEL_2X2",                [(+1, "PANEL_2X4"), (-2, "PANEL_2X2")]),
    ("PANEL_2X4 vs 2*PANEL_1X4",                [(+1, "PANEL_2X4"), (-2, "PANEL_1X4")]),
    ("PANEL_4X4 vs 2*PANEL_2X4",                [(+1, "PANEL_4X4"), (-2, "PANEL_2X4")]),
    ("PANEL_4X4 vs 4*PANEL_2X2",                [(+1, "PANEL_4X4"), (-4, "PANEL_2X2")]),
    ("PANEL_2X2 vs 2*PANEL_1X2",                [(+1, "PANEL_2X2"), (-2, "PANEL_1X2")]),
]


def load_panels(day: int) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
    panels = df[df["product"].str.startswith("PANEL_")]
    return panels.pivot_table(index="timestamp", columns="product", values="mid_price")


def evaluate_relation(name: str, terms: list[tuple[int, str]], pivot: pd.DataFrame) -> dict:
    spread = sum(coef * pivot[product] for coef, product in terms)
    return {
        "name": name,
        "mean": spread.mean(),
        "std": spread.std(),
        "min": spread.min(),
        "max": spread.max(),
        "abs_mean": abs(spread.mean()),
    }


def main() -> None:
    print("=" * 86)
    print("H3: PANEL composition relationships (basket arb candidates)")
    print("=" * 86)
    print("If a relation holds, mean ≈ 0 and std reveals oscillation amplitude.")
    print("If mean is far from 0, the relation does not hold (no constant pricing rule).")
    print()

    print(f"{'relation':<42} {'day':>4} {'mean':>10} {'std':>9} {'min':>9} {'max':>9}")
    print("-" * 86)
    for day in DAYS:
        pivot = load_panels(day).dropna()
        for name, terms in RELATIONS:
            r = evaluate_relation(name, terms, pivot)
            print(f"{r['name']:<42} {day:>4d} {r['mean']:>+10.1f} {r['std']:>9.1f} "
                  f"{r['min']:>+9.0f} {r['max']:>+9.0f}")
        print()

    print("Interpretation:")
    print("  - mean ≈ 0 with low std → tight basket; arb when spread deviates")
    print("  - mean ≈ 0 with high std → noisy but mean-reverting; potential pair trade")
    print("  - mean far from 0 → not a basket; products priced independently")


if __name__ == "__main__":
    main()
