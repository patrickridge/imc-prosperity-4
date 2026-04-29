"""H5b: Microchip lead-lag at longer windows.

H5 tested lags 1-5 across all 10 categories and found nothing (best |corr|
0.022). Giovanni claims microchips have lead-lag; this script extends the
search to lags 10, 25, 50, 100, 200 specifically for the 5 microchip
products to confirm or refute.

Tests every directional pair (5 leaders x 4 followers = 20 pairs) at each
lag, reports the strongest signal per pair.

Run as: python3 research/round5_h5b_microchip_lags.py
"""
from __future__ import annotations

from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
LAGS = [1, 5, 10, 25, 50, 100, 200]
MIN_ABS_CORR = 0.05
PRODUCTS = ["MICROCHIP_CIRCLE", "MICROCHIP_OVAL", "MICROCHIP_SQUARE",
            "MICROCHIP_RECTANGLE", "MICROCHIP_TRIANGLE"]


def load_returns() -> pd.DataFrame:
    frames = []
    for day in DAYS:
        df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
        sub = df[df["product"].isin(PRODUCTS)]
        pivot = sub.pivot_table(index="timestamp", columns="product", values="mid_price")
        frames.append(pivot)
    full = pd.concat(frames)
    return np.log(full).diff().dropna()


def lagged_corr(leader: pd.Series, follower: pd.Series, lag: int) -> float:
    return leader.shift(lag).corr(follower)


def main() -> None:
    print("=" * 78)
    print("H5b: Microchip lead-lag at longer windows")
    print("=" * 78)
    print(f"Tests every directional pair at lags {LAGS}.")
    print(f"|corr| > {MIN_ABS_CORR} = potentially actionable.")
    print()

    returns = load_returns()
    rows = []
    for leader, follower in permutations(PRODUCTS, 2):
        for lag in LAGS:
            corr = lagged_corr(returns[leader], returns[follower], lag)
            rows.append({
                "leader": leader.replace("MICROCHIP_", ""),
                "follower": follower.replace("MICROCHIP_", ""),
                "lag": lag,
                "corr": corr,
            })

    df = pd.DataFrame(rows)
    df["abs_corr"] = df["corr"].abs()
    df = df.sort_values("abs_corr", ascending=False)

    print("Top 15 strongest leader -> follower correlations across all lags:")
    print()
    cols = ["leader", "follower", "lag", "corr"]
    print(df.head(15)[cols].to_string(index=False, float_format=lambda x: f"{x:+.3f}"))
    print()

    actionable = df[df["abs_corr"] >= MIN_ABS_CORR]
    print(f"Pairs with |corr| >= {MIN_ABS_CORR}: {len(actionable)} of {len(df)}")
    if actionable.empty:
        print()
        print("Verdict: H5 result confirmed even at longer lags. No microchip lead-lag.")
    else:
        print()
        print("Strongest pairs to investigate:")
        print(actionable.head(10)[cols].to_string(index=False,
            float_format=lambda x: f"{x:+.3f}"))


if __name__ == "__main__":
    main()
