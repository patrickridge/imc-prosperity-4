"""H1 (Round 5): Are PEBBLES_XL/XS and MICROCHIP_SQUARE/OVAL stable pair trades?

The 3-day exploration showed:
  PEBBLES_XL +60.7%, PEBBLES_XS −39.6%, correlation −0.83
  MICROCHIP_SQUARE +36.3%, MICROCHIP_OVAL −44.8%

A −0.83 correlation across 3 days could be:
  (a) Two independent products with opposing drifts (lucky coincidence) → no edge
  (b) A genuine inverse relationship → tradeable pair (long/short basket)

This test splits the data day-by-day and checks:
  - Within-day correlation per pair
  - Within-day drift signs (do they remain opposite?)
  - Hedge ratio stability (does the inverse slope stay constant?)

Run as: python3 research/round5_h1_pair_drift.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
PAIRS = [
    ("PEBBLES_XL", "PEBBLES_XS"),
    ("MICROCHIP_SQUARE", "MICROCHIP_OVAL"),
]


def load_day(day: int) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")


def pivot_pair(df: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    sub = df[df["product"].isin([a, b])][["timestamp", "product", "mid_price"]]
    return sub.pivot(index="timestamp", columns="product", values="mid_price").dropna()


def report_pair(a: str, b: str) -> None:
    print(f"--- {a}  vs  {b} ---")
    print(f"{'day':>4} {'corr':>7} {'a_drift_pct':>13} {'b_drift_pct':>13} "
          f"{'hedge_ratio':>13} {'pair_pnl_per_unit':>20}")

    all_a, all_b = [], []
    for day in DAYS:
        df = load_day(day)
        pair = pivot_pair(df, a, b)
        if pair.empty:
            print(f"  day {day}: missing data")
            continue

        corr = pair[a].corr(pair[b])
        a_drift = (pair[a].iloc[-1] - pair[a].iloc[0]) / pair[a].iloc[0] * 100
        b_drift = (pair[b].iloc[-1] - pair[b].iloc[0]) / pair[b].iloc[0] * 100

        # OLS slope: b on a (delta-b per delta-a)
        a_diff = pair[a].diff().dropna()
        b_diff = pair[b].diff().dropna()
        n = min(len(a_diff), len(b_diff))
        if n > 1:
            beta = np.cov(a_diff[:n], b_diff[:n])[0, 1] / np.var(a_diff[:n])
        else:
            beta = float("nan")

        # Long-A short-B with hedge ratio = -beta
        # Per-unit pair PnL = (a_end - a_start) + beta * (b_end - b_start)  [shorting b]
        per_unit = (pair[a].iloc[-1] - pair[a].iloc[0]) - beta * (
            pair[b].iloc[-1] - pair[b].iloc[0])

        print(f"{day:>4d} {corr:>+7.3f} {a_drift:>+12.2f}% {b_drift:>+12.2f}% "
              f"{beta:>+13.3f} {per_unit:>+19.2f}")

        all_a.append(pair[a])
        all_b.append(pair[b])

    if all_a:
        full_a = pd.concat(all_a)
        full_b = pd.concat(all_b)
        full_corr = full_a.corr(full_b)
        print(f"  combined corr: {full_corr:+.3f}")
    print()


def main() -> None:
    print("=" * 78)
    print("H1: Pair-trade stability — PEBBLES_XL/XS, MICROCHIP_SQUARE/OVAL")
    print("=" * 78)
    print("Hypothesis: if correlation stays strongly negative WITHIN each day,")
    print("the pair is tradeable. If it flips sign or weakens day-to-day,")
    print("the 3-day correlation was coincidental and not actionable.")
    print()
    for a, b in PAIRS:
        report_pair(a, b)


if __name__ == "__main__":
    main()
