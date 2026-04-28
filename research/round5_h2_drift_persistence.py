"""H2 (Round 5): Are the big 3-day drifts steady trends or single-day jumps?

The 3-day drift table showed PEBBLES_XL +60.7%, MICROCHIP_OVAL -44.8%, etc.
But "+60% over 3 days" can mean very different things:
  - Steady trend: +20% / day every day  → trade with the trend daily
  - Single jump: +5% / +50% / +5%       → news-driven, hard to time
  - Reversal:    +30% / -10% / +40%     → don't trust 3-day stats at all

This test breaks each big mover into per-day drifts.

Run as: python3 research/round5_h2_drift_persistence.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]

# Top movers identified by round5_explore.py over 3 days
BIG_MOVERS = [
    "PEBBLES_XL", "PEBBLES_XS",
    "MICROCHIP_OVAL", "MICROCHIP_SQUARE",
    "OXYGEN_SHAKE_GARLIC",
    "GALAXY_SOUNDS_BLACK_HOLES",
    "UV_VISOR_AMBER",
    "ROBOT_IRONING",
]

CONSISTENT_TREND_THRESHOLD = 0.66  # at least 2 of 3 days same sign as overall


def load_day(day: int) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")


def per_day_drift(product: str) -> dict[int, float]:
    drifts = {}
    for day in DAYS:
        df = load_day(day)
        sub = df[df["product"] == product]["mid_price"].dropna()
        if len(sub) < 2:
            continue
        first, last = sub.iloc[0], sub.iloc[-1]
        drifts[day] = (last - first) / first * 100
    return drifts


def classify(drifts: dict[int, float]) -> str:
    values = list(drifts.values())
    if not values:
        return "no data"

    overall = sum(values)  # rough proxy for total drift sign
    same_sign = sum(1 for v in values if (v > 0) == (overall > 0))
    fraction = same_sign / len(values)

    if fraction >= CONSISTENT_TREND_THRESHOLD:
        if min(abs(v) for v in values) > 5:
            return "steady trend"
        return "weak trend"
    if max(abs(v) for v in values) > 2 * sorted(abs(v) for v in values)[-2]:
        return "single-day jump"
    return "noisy / reversing"


def main() -> None:
    print("=" * 78)
    print("H2: Drift persistence — does the 3-day move come from a steady trend?")
    print("=" * 78)
    print(f"{'product':<28} {'day 2':>9} {'day 3':>9} {'day 4':>9} "
          f"{'sum':>9}  classification")
    print("-" * 78)

    for product in BIG_MOVERS:
        drifts = per_day_drift(product)
        d2 = drifts.get(2, float("nan"))
        d3 = drifts.get(3, float("nan"))
        d4 = drifts.get(4, float("nan"))
        total = sum(drifts.values())
        verdict = classify(drifts)
        print(f"{product:<28} {d2:>+8.2f}% {d3:>+8.2f}% {d4:>+8.2f}% "
              f"{total:>+8.2f}%  {verdict}")

    print()
    print("Implication: 'steady trend' products are tradeable with directional bias.")
    print("'single-day jump' products lock in profit on one day only — risky to bet on day-N.")
    print("'noisy / reversing' products burn directional bets — market-make only.")


if __name__ == "__main__":
    main()
