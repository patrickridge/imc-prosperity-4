"""H5 (Round 5): Within each category, which product moves first?

For each of the 10 categories (5 products each), compute cross-correlation
of returns at lags ±10 ticks. The product whose returns lead the others
is the category 'leader' — its moves predict the followers.

Tradeable when:
  - One product reliably leads with high cross-correlation
  - The lag is consistent day-to-day (not artifact)

Run as: python3 research/round5_h5_lead_lag.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
LAG_RANGE = list(range(-5, 6))   # leader leads by at most 5 ticks
MIN_ABS_LEAD = 0.10              # below this we don't claim a leader

CATEGORIES = {
    "GALAXY_SOUNDS": ["DARK_MATTER", "BLACK_HOLES", "PLANETARY_RINGS", "SOLAR_WINDS", "SOLAR_FLAMES"],
    "SLEEP_POD":     ["SUEDE", "LAMB_WOOL", "POLYESTER", "NYLON", "COTTON"],
    "MICROCHIP":     ["CIRCLE", "OVAL", "SQUARE", "RECTANGLE", "TRIANGLE"],
    "PEBBLES":       ["XS", "S", "M", "L", "XL"],
    "ROBOT":         ["VACUUMING", "MOPPING", "DISHES", "LAUNDRY", "IRONING"],
    "UV_VISOR":      ["YELLOW", "AMBER", "ORANGE", "RED", "MAGENTA"],
    "TRANSLATOR":    ["SPACE_GRAY", "ASTRO_BLACK", "ECLIPSE_CHARCOAL", "GRAPHITE_MIST", "VOID_BLUE"],
    "PANEL":         ["1X2", "2X2", "1X4", "2X4", "4X4"],
    "OXYGEN_SHAKE":  ["MORNING_BREATH", "EVENING_BREATH", "MINT", "CHOCOLATE", "GARLIC"],
    "SNACKPACK":     ["CHOCOLATE", "VANILLA", "PISTACHIO", "STRAWBERRY", "RASPBERRY"],
}


def load_returns(category: str) -> pd.DataFrame:
    products = [f"{category}_{v}" for v in CATEGORIES[category]]
    frames = []
    for day in DAYS:
        df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
        sub = df[df["product"].isin(products)]
        pivot = sub.pivot_table(index="timestamp", columns="product", values="mid_price")
        pivot["__day"] = day
        frames.append(pivot)
    full = pd.concat(frames)
    log_returns = np.log(full.drop(columns="__day")).diff()
    return log_returns.dropna()


def best_lead_pair(returns: pd.DataFrame) -> tuple[str, str, int, float]:
    """Return (leader, follower, lag, correlation). lag>0 means leader precedes follower."""
    products = returns.columns.tolist()
    best = ("", "", 0, 0.0)
    for leader in products:
        for follower in products:
            if leader == follower:
                continue
            for lag in LAG_RANGE:
                if lag <= 0:
                    continue
                shifted = returns[leader].shift(lag)
                corr = shifted.corr(returns[follower])
                if abs(corr) > abs(best[3]):
                    best = (leader, follower, lag, corr)
    return best


def report_category(category: str) -> None:
    returns = load_returns(category)
    if returns.empty:
        print(f"{category}: no data")
        return

    leader, follower, lag, corr = best_lead_pair(returns)
    leader_short = leader.replace(category + "_", "")
    follower_short = follower.replace(category + "_", "")
    flag = "(actionable)" if abs(corr) >= MIN_ABS_LEAD else "(weak)"
    print(f"{category:<14} {leader_short:>16} → {follower_short:<16} "
          f"lag={lag:+d}  corr={corr:+.3f}  {flag}")


def main() -> None:
    print("=" * 84)
    print("H5: Within-category lead-lag — which product moves first?")
    print("=" * 84)
    print("Strongest forward-lagged correlation found per category (3 days combined).")
    print(f"lag k means leader's return at t predicts follower at t+k.")
    print(f"Threshold for 'actionable': |corr| >= {MIN_ABS_LEAD}")
    print()
    print(f"{'category':<14} {'leader':>16}   {'follower':<16}  {'lag':>5}   {'corr':>7}  status")
    print("-" * 84)
    for category in CATEGORIES:
        report_category(category)


if __name__ == "__main__":
    main()
